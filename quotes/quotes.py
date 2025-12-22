import discord
import io
import textwrap
import aiohttp
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import pagify

from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

from .views import QuoteListView, ConfirmResetView, RemoveQuoteView

class Quotes(commands.Cog):
    """Force people to relive the stupid/funny shit they say"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9384729384, force_registration=True)

        default_guild = {
            "quotes": [],
            "quotes_channel": None
        }

        self.config.register_guild(**default_guild)

    FONT_PATH = "quotes/fonts/NotoSans-Regular.ttf"
    
    # ---------- INTERNAL HELPERS ----------
    async def _render_quote_image(self, message: discord.Message):
        WIDTH = 1000
        PADDING = 40
        AVATAR_SIZE = 96
        MAX_TEXT_WIDTH = 48

        try:
            font_msg = ImageFont.truetype(self.FONT_PATH, 30)
            font_name = ImageFont.truetype(self.FONT_PATH, 26)
            font_user = ImageFont.truetype(self.FONT_PATH, 20)
            font_server = ImageFont.truetype(self.FONT_PATH, 18)
        except Exception:
            font_msg = font_name = font_user = font_server = ImageFont.load_default()

        wrapped_text = textwrap.fill(message.content, width=MAX_TEXT_WIDTH)
        text_lines = wrapped_text.count("\n") + 1

        TEXT_HEIGHT = text_lines * 36
        HEIGHT = max(300, TEXT_HEIGHT + 160)

        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # ---------- AVATAR ----------
        async with aiohttp.ClientSession() as session:
            async with session.get(message.author.display_avatar.url) as resp:
            avatar_bytes = await resp.read()

        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGB")
        avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))
        img.paste(avatar, (PADDING, PADDING))

        # ---------- TEXT ----------
        text_x = PADDING * 2 + AVATAR_SIZE
        text_y = PADDING

        with Pilmoji(img) as pilmoji:
            pilmoji.text(
                (text_x, text_y),
                wrapped_text,
                font=font_msg,
                fill=(255, 255, 255),
                spacing=6
            )

            name_y = text_y + TEXT_HEIGHT + 20

            pilmoji.text(
                (text_x, name_y),
                message.author.display_name,
                font=font_name,
                fill=(255, 255, 255)
            )

            pilmoji.text(
                (text_x, name_y + 32),
                f"@{message.author.name}",
                font=font_user,
                fill=(180, 180, 180)
            )

        # ---------- SERVER NAME ----------
        server_text = message.guild.name
        sw, sh = draw.textsize(server_text, font=font_server)
        draw.text(
            (WIDTH - sw - PADDING, HEIGHT - sh - PADDING),
            server_text,
            fill=(160, 160, 160),
            font=font_server
        )

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return discord.File(buffer, filename="quote.png")

    async def _quote_exists(self, guild, message_id):
        quotes = await self.config.guild(guild).quotes()
        return next((q for q in quotes if q["message_id"] == message_id), None)

    async def _create_quote(self, ctx, target_message):
    existing = await self._quote_exists(ctx.guild, target_message.id)
    if existing:
        await ctx.send(f"Quote already exists: {existing['jump_url']}")
        return

    quotes = await self.config.guild(ctx.guild).quotes()
    number = len(quotes) + 1

    file = await self._render_quote_image(target_message)

    channel_id = await self.config.guild(ctx.guild).quotes_channel()
    target_channel = ctx.guild.get_channel(channel_id) if channel_id else ctx.channel

    sent = await target_channel.send(
        file=file,
        view=RemoveQuoteView(self, ctx.guild, number)
    )

    quotes.append({
        "number": number,
        "author_id": target_message.author.id,
        "content": target_message.content,
        "message_id": target_message.id,
        "jump_url": sent.jump_url
    })

    await self.config.guild(ctx.guild).quotes.set(quotes)
    await ctx.send(f"Quote saved: {sent.jump_url}")
    
    # ---------- COMMANDS ----------

@commands.command(aliases=["q"])
async def quote(self, ctx):
    if not ctx.message.reference:
        await ctx.send("You must reply to a message to quote it.")
        return

    target = await ctx.channel.fetch_message(
        ctx.message.reference.message_id
    )

    await target.add_reaction("💬")
    await self._create_quote(ctx, target)

    @commands.has_permissions(administrator=True)
    @commands.command(aliases=["qset"])
    async def set_quotes(self, ctx, channel: discord.TextChannel):
        await self.config.guild(ctx.guild).quotes_channel.set(channel.id)
        await ctx.send(f"Quotes channel set to {channel.mention}")

    @commands.has_permissions(administrator=True)
    @commands.command(aliases=["qunset"])
    async def set_quotes_removechannel(self, ctx):
        await self.config.guild(ctx.guild).quotes_channel.set(None)
        await ctx.send("Quotes channel unset.")

    @commands.command(aliases=["qlist"])
    async def seequotes(self, ctx, *members: discord.Member):
        quotes = await self.config.guild(ctx.guild).quotes()
        if members:
            ids = {m.id for m in members}
            quotes = [q for q in quotes if q["author_id"] in ids]

        if not quotes:
            return await ctx.send("No quotes found.")

        view = QuoteListView(quotes)
        await ctx.send(embed=view.make_embed(), view=view)

    @commands.has_permissions(administrator=True)
    @commands.command(aliases=["qreset"])
    async def reset_quotes(self, ctx):
        await ctx.send(
            "Are you sure you want to reset ALL quotes?",
            view=ConfirmResetView(self, ctx.guild)
        )

    # ---------- LISTENER ----------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.emoji.name != "💬":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if await self._quote_exists(guild, message.id):
            return

        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        ctx = await self.bot.get_context(message)
        ctx.author = member
        ctx.guild = guild
        ctx.channel = channel

        await self._create_quote(ctx, message)
