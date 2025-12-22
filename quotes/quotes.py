import discord
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import pagify
from PIL import Image, ImageDraw, ImageFont
import io

from .views import QuoteListView, ConfirmResetView, RemoveQuoteView

class Quotes(commands.Cog):
    """Quote messages into images."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9384729384, force_registration=True)

        default_guild = {
            "quotes": [],
            "quotes_channel": None
        }

        self.config.register_guild(**default_guild)

    # ---------- INTERNAL HELPERS ----------

    async def _render_quote_image(self, message: discord.Message):
        img = Image.new("RGB", (900, 300), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
            small = ImageFont.truetype("DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()
            small = ImageFont.load_default()

        text = message.content[:500]
        draw.text((40, 40), text, fill=(255, 255, 255), font=font)
        draw.text((40, 220), f"{message.author.display_name} (@{message.author.name})",
                  fill=(200, 200, 200), font=small)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return discord.File(buf, filename="quote.png")

    async def _quote_exists(self, guild, message_id):
        quotes = await self.config.guild(guild).quotes()
        return next((q for q in quotes if q["message_id"] == message_id), None)

    # ---------- COMMANDS ----------

    @commands.command(aliases=["q"])
    async def quote(self, ctx: commands.Context):
        if not ctx.message.reference:
            return await ctx.send("You must reply to a message to quote it.")

        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)

        existing = await self._quote_exists(ctx.guild, msg.id)
        if existing:
            return await ctx.send(f"Quote already exists: {existing['jump_url']}")

        await msg.add_reaction("💬")

        quotes = await self.config.guild(ctx.guild).quotes()
        number = len(quotes) + 1

        file = await self._render_quote_image(msg)

        channel_id = await self.config.guild(ctx.guild).quotes_channel()
        target = ctx.guild.get_channel(channel_id) if channel_id else ctx.channel

        sent = await target.send(file=file, view=RemoveQuoteView(self, ctx.guild, number))

        quotes.append({
            "number": number,
            "author_id": msg.author.id,
            "content": msg.content,
            "message_id": msg.id,
            "jump_url": sent.jump_url
        })

        await self.config.guild(ctx.guild).quotes.set(quotes)
        await ctx.send(f"Quote saved: {sent.jump_url}")

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
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if await self._quote_exists(guild, message.id):
            return

        ctx = await self.bot.get_context(message)
        await self.quote(ctx)
