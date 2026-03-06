import discord
from redbot.core import commands, bot, Config
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
from datetime import datetime
from typing import Optional

class Quote(commands.Cog):
    """Quote messages in a stylized format."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        
        # Config storage
        self.config = Config.get_conf(self, identifier=1234567895, force_registration=True)
        self.config.register_guild(
            quotes_channel_id=None,
            log_channel_id=None
        )
    
    async def log_action(self, guild_id: int, message: str):
        """Log an action to the configured log channel."""
        log_channel_id = await self.config.guild_from_id(guild_id).log_channel_id()
        if log_channel_id:
            try:
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(message)
            except Exception:
                pass
        print(f"[QUOTE LOG - Guild {guild_id}] {message}")
    
    def create_quote_image(
        self,
        author_name: str,
        author_avatar: bytes,
        message_content: str,
        timestamp: datetime,
        color: discord.Color = None
    ) -> io.BytesIO:
        """
        Create a stylized quote image.
        
        Args:
            author_name: Name of the message author
            author_avatar: Avatar image bytes
            message_content: The message content to quote
            timestamp: When the message was sent
            color: Color of the accent bar (uses author's color if available)
        
        Returns:
            BytesIO object containing the quote image
        """
        # Image dimensions
        width = 600
        padding = 20
        text_width = width - (padding * 2)
        
        # Colors
        bg_color = (36, 37, 40)  # Dark Discord background
        text_color = (220, 221, 222)  # Light text
        accent_color = (88, 165, 255) if color is None else color.to_rgb()  # Blue accent
        
        # Load and resize avatar
        avatar_img = Image.open(io.BytesIO(author_avatar)).convert("RGBA")
        avatar_size = 50
        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
        
        # Create base image
        img = Image.new("RGB", (width, 100), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Try to load a nice font, fall back to default if not available
        try:
            name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
            content_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            timestamp_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        except (OSError, IOError):
            # Fallback to default font
            name_font = ImageFont.load_default()
            content_font = ImageFont.load_default()
            timestamp_font = ImageFont.load_default()
        
        # Wrap text
        wrapped_lines = []
        words = message_content.split()
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=content_font)
            if bbox[2] - bbox[0] > text_width - 20:  # Account for avatar space
                if current_line:
                    wrapped_lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        
        if current_line:
            wrapped_lines.append(current_line)
        
        # Limit to reasonable number of lines
        wrapped_lines = wrapped_lines[:10]
        
        # Calculate final image height
        line_height = 18
        content_height = len(wrapped_lines) * line_height + 10
        metadata_height = 25
        total_height = padding + avatar_size + padding + content_height + metadata_height + padding
        
        # Recreate image with proper height
        img = Image.new("RGB", (width, total_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw accent bar on the left
        bar_width = 4
        draw.rectangle([(0, 0), (bar_width, total_height)], fill=accent_color)
        
        # Draw avatar
        avatar_x = padding
        avatar_y = padding
        img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
        
        # Draw author name
        name_x = avatar_x + avatar_size + padding
        name_y = avatar_y
        draw.text((name_x, name_y), author_name, fill=text_color, font=name_font)
        
        # Draw timestamp below name
        timestamp_str = timestamp.strftime("%m/%d/%Y %I:%M %p")
        draw.text((name_x, name_y + 18), timestamp_str, fill=(120, 120, 120), font=timestamp_font)
        
        # Draw message content
        content_y = avatar_y + avatar_size + padding
        for i, line in enumerate(wrapped_lines):
            y_pos = content_y + (i * line_height)
            draw.text((padding + 10, y_pos), line, fill=text_color, font=content_font)
        
        # Convert to bytes
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf
    
    @commands.hybrid_group(name="quotecfg", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def quotecfg(self, ctx: commands.Context):
        """Quote configuration settings."""
        quotes_channel_id = await self.config.guild(ctx.guild).quotes_channel_id()
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        
        quotes_channel_str = f"<#{quotes_channel_id}>" if quotes_channel_id else "Not set"
        log_channel_str = f"<#{log_channel_id}>" if log_channel_id else "Not set"
        
        embed = discord.Embed(
            title="Quote Configuration",
            description="Current quote settings for this server",
            color=discord.Color.blue()
        )
        embed.add_field(name="Quotes Channel", value=quotes_channel_str, inline=False)
        embed.add_field(name="Log Channel", value=log_channel_str, inline=False)
        embed.add_field(
            name="Commands",
            value=(
                "`quotecfg quoteschannel <channel>` - Set quotes channel\n"
                "`quotecfg quoteschannel clear` - Clear quotes channel\n"
                "`quotecfg logchannel <channel>` - Set log channel\n"
                "`quotecfg logchannel clear` - Clear log channel"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @quotecfg.group(name="quoteschannel", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def quotecfg_quoteschannel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the quotes channel."""
        if channel is None:
            # Show current quotes channel
            quotes_channel_id = await self.config.guild(ctx.guild).quotes_channel_id()
            if quotes_channel_id:
                await ctx.send(f"Current quotes channel: <#{quotes_channel_id}>", delete_after=5)
            else:
                await ctx.send("No quotes channel is set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).quotes_channel_id.set(channel.id)
        await ctx.send(f"✅ Quotes channel set to {channel.mention}", delete_after=5)
        await self.log_action(ctx.guild.id, f"Quotes channel set to {channel.name}")
    
    @quotecfg_quoteschannel_group.command(name="clear", description="Clear the quotes channel")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def quotecfg_quoteschannel_clear(self, ctx: commands.Context):
        """Clear the quotes channel setting."""
        quotes_channel_id = await self.config.guild(ctx.guild).quotes_channel_id()
        
        if not quotes_channel_id:
            await ctx.send("❌ No quotes channel is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).quotes_channel_id.clear()
        await ctx.send("✅ Quotes channel has been cleared.", delete_after=5)
        await self.log_action(ctx.guild.id, "Quotes channel cleared")
    
    @quotecfg.group(name="logchannel", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def quotecfg_logchannel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the log channel."""
        if channel is None:
            # Show current log channel
            log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
            if log_channel_id:
                await ctx.send(f"Current log channel: <#{log_channel_id}>", delete_after=5)
            else:
                await ctx.send("No log channel is set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id)
        await ctx.send(f"✅ Log channel set to {channel.mention}", delete_after=5)
    
    @quotecfg_logchannel_group.command(name="clear", description="Clear the log channel")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def quotecfg_logchannel_clear(self, ctx: commands.Context):
        """Clear the log channel setting."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        
        if not log_channel_id:
            await ctx.send("❌ No log channel is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).log_channel_id.clear()
        await ctx.send("✅ Log channel has been cleared.", delete_after=5)
    
    @commands.hybrid_command(name="quote", aliases=["q"], description="Quote a message in a stylized format")
    async def quote(self, ctx: commands.Context, message: Optional[discord.Message] = None):
        """
        Quote a message in a stylized format similar to the 'Make it a Quote' bot.
        
        Reply to a message or provide a message ID/link to quote it.
        The quote will be sent to the quotes channel if one is configured.
        """
        # Get the message to quote
        if message is None:
            # Check if this is a reply
            if ctx.message.reference:
                try:
                    message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                except discord.NotFound:
                    await ctx.send("❌ Could not find the message you replied to.", delete_after=5)
                    return
            else:
                await ctx.send("❌ Reply to a message or provide a message ID to quote it.", delete_after=5)
                return
        
        # Validate message has content
        if not message.content and not message.embeds and not message.attachments:
            await ctx.send("❌ Cannot quote a message with no content.", delete_after=5)
            return
        
        # Use message content or fallback to embed description
        quote_content = message.content
        if not quote_content and message.embeds:
            quote_content = message.embeds[0].description or "[Embed]"
        if not quote_content:
            quote_content = "[Media attachment]"
        
        # Get author avatar
        try:
            avatar_bytes = await message.author.display_avatar.read()
        except Exception:
            # Fallback if avatar can't be fetched
            avatar_bytes = await self.bot.user.display_avatar.read()
        
        # Get author's color from roles
        author_color = None
        if isinstance(message.author, discord.Member) and message.author.color:
            author_color = message.author.color
        
        # Generate quote image
        try:
            quote_image = self.create_quote_image(
                author_name=message.author.display_name,
                author_avatar=avatar_bytes,
                message_content=quote_content,
                timestamp=message.created_at,
                color=author_color
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to create quote image: {e}", delete_after=5)
            return
        
        # Create the file
        quote_file = discord.File(quote_image, filename="quote.png")
        
        # Prepare quote info embed for the quotes channel
        embed = None
        quotes_channel_id = await self.config.guild(ctx.guild).quotes_channel_id()
        if quotes_channel_id:
            embed = discord.Embed(
                description=f"**{message.author.display_name}** in {message.channel.mention}",
                color=author_color or discord.Color.blue(),
                timestamp=message.created_at
            )
            embed.set_footer(text=f"Original message ID: {message.id}")
        
        # Send to current channel
        try:
            await ctx.send(
                file=quote_file,
                reference=ctx.message,
                mention_author=False
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to send quote: {e}", delete_after=5)
            return
        
        # Send to quotes channel if configured
        if quotes_channel_id:
            try:
                quotes_channel = self.bot.get_channel(quotes_channel_id)
                if quotes_channel:
                    # Re-read the file since it was already sent
                    quote_image.seek(0)
                    quote_file_archive = discord.File(quote_image, filename="quote.png")
                    
                    await quotes_channel.send(
                        embed=embed,
                        file=quote_file_archive
                    )
                    await self.log_action(
                        ctx.guild.id,
                        f"Quote created by {ctx.author.display_name} from {message.author.display_name}'s message"
                    )
                else:
                    await self.log_action(ctx.guild.id, f"Quotes channel {quotes_channel_id} not found")
            except discord.Forbidden:
                await ctx.send(
                    "⚠️ Quote created but couldn't send to quotes channel (no permissions).",
                    delete_after=5
                )
                await self.log_action(ctx.guild.id, f"Failed to send quote to channel {quotes_channel_id} - no permissions")
            except Exception as e:
                await ctx.send(
                    f"⚠️ Quote created but failed to send to quotes channel: {e}",
                    delete_after=5
                )
                await self.log_action(ctx.guild.id, f"Failed to send quote to channel {quotes_channel_id}: {e}")

async def setup(bot: bot.Red):
    """Load the Quote cog."""
    await bot.add_cog(Quote(bot))
