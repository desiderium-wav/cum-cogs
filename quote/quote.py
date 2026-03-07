import discord
from redbot.core import commands, bot, Config
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
from datetime import datetime
from typing import Optional

class Quote(commands.Cog):
    """Quote messages in a stylized format."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        self.quote_authors = {}  # Track {message_id: original_author_id}
        
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
        message_content: str,
        author_name: str,
        author_username: str,
        author_avatar: bytes,
        timestamp: datetime,
        color: discord.Color = None,
        message_id: int = None
    ) -> io.BytesIO:
        """
        Create a stylized quote image with large text, centered layout, and minimal dead space.
        
        Args:
            message_content: The message content to quote
            author_name: Display name of the message author
            author_username: Username of the message author
            author_avatar: Avatar image bytes
            timestamp: When the message was sent
            color: Color accent (not used in this version)
            message_id: Message ID for tracking (not displayed in this version)
        
        Returns:
            BytesIO object containing the quote image
        """
        # Load and process avatar first to determine sizing
        avatar_img = Image.open(io.BytesIO(author_avatar)).convert("RGBA")
        
        # Apply black and white filter
        avatar_bw = ImageOps.grayscale(avatar_img).convert("RGBA")
        avatar_size = 250  # Large avatar
        avatar_bw = avatar_bw.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
        
        # Colors
        bg_color = (0, 0, 0)  # Pure black
        text_color = (220, 221, 222)  # Light text
        secondary_text = (180, 180, 180)  # Slightly lighter secondary text
        
        # Load fonts - use larger sizes
        try:
            content_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 1600)
            author_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 600)
            username_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 200)
        except (OSError, IOError):
            content_font = ImageFont.load_default()
            author_font = ImageFont.load_default()
            username_font = ImageFont.load_default()
        
        # Wrap message content with large font
        max_content_width = 400  # Maximum width for text
        words = message_content.split()
        lines = []
        current_line = ""
        
        draw_temp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw_temp.textbbox((0, 0), test_line, font=content_font)
            line_width = bbox[2] - bbox[0]
            
            if line_width > max_content_width and current_line:
                lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        
        if current_line:
            lines.append(current_line)
        
        # Limit lines
        lines = lines[:8]
        
        # Calculate dimensions
        padding = 60
        avatar_to_text = 50
        line_height = 40
        
        # Calculate text block height
        text_height = len(lines) * line_height
        
        # Calculate author block height (name + username with minimal spacing)
        author_block_height = 140 + 20 + 100  # author font + minimal gap + username font
        
        # Calculate total content height
        total_content_height = text_height + 30 + author_block_height  # 40 is spacing between text and author
        
        # Image dimensions - avatar on left, text on right, centered vertically
        img_width = avatar_size + avatar_to_text + 200 + padding * 2
        img_height = max(total_content_height + padding * 2, avatar_size + padding * 2)
        
        # Create image
        img = Image.new("RGB", (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Center vertically
        vertical_center = img_height // 2
        
        # Avatar position - left side, vertically centered
        avatar_x = padding
        avatar_y = vertical_center - (avatar_size // 2)
        img.paste(avatar_bw, (avatar_x, avatar_y), avatar_bw)
        
        # Text position - right of avatar, vertically centered around the middle
        text_x = avatar_x + avatar_size + avatar_to_text
        text_block_top = vertical_center - (total_content_height // 2)
        
        # Draw message content lines
        for i, line in enumerate(lines):
            y = text_block_top + (i * line_height)
            draw.text((text_x, y), line, fill=text_color, font=content_font)
        
        # Draw author info below message with minimal spacing
        author_y = text_block_top + text_height + 40
        
        # Author name
        draw.text((text_x, author_y), f"- {author_name}", fill=text_color, font=author_font)
        
        # Username below author name with minimal spacing
        draw.text((text_x, author_y + 20), f"@{author_username}", fill=secondary_text, font=username_font)
        
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
    
    class QuoteView(discord.ui.View):
        """Interactive view for quote actions."""
        
        def __init__(self, original_message: discord.Message, quote_sender: discord.User, cog):
            super().__init__(timeout=None)
            self.original_message = original_message
            self.quote_sender = quote_sender
            self.cog = cog
            
            # Add jump button with URL
            jump_button = discord.ui.Button(
                label="Jump to original message",
                style=discord.ButtonStyle.link,
                url=original_message.jump_url
            )
            self.add_item(jump_button)
        
        @discord.ui.button(label="Remove my Quote", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            """Button to remove the quote."""
            # Only allow the quote sender to remove it
            if interaction.user.id != self.quote_sender.id:
                await interaction.response.send_message(
                    "❌ Only the user who created this quote can remove it.",
                    ephemeral=True
                )
                return
            
            try:
                # Delete the quote message
                await interaction.message.delete()
                await self.cog.log_action(
                    interaction.guild.id,
                    f"Quote removed by {interaction.user.display_name}"
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to delete this message.",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Failed to remove quote: {e}",
                    ephemeral=True
                )
    
    @commands.hybrid_command(name="quote", aliases=["q"], description="Quote a message in a stylized format")
    async def quote(self, ctx: commands.Context, message: Optional[discord.Message] = None):
        """
        Quote a message in a stylized format similar to the 'Make it a Quote' bot.
        
        Reply to a message or provide a message ID/link to quote it.
        The quote will be sent to the quotes channel if one is configured.
        """
        # Get the message to quote
        if message is None:
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
            avatar_bytes = await self.bot.user.display_avatar.read()
        
        # Generate quote image
        try:
            quote_image = self.create_quote_image(
                message_content=quote_content,
                author_name=message.author.display_name,
                author_username=message.author.name,
                author_avatar=avatar_bytes,
                timestamp=message.created_at,
                message_id=message.id
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to create quote image: {e}", delete_after=5)
            return
        
        # Create the file
        quote_file = discord.File(quote_image, filename="quote.png")
        
        # Create view with buttons
        view = self.QuoteView(message, ctx.author, self)
        
        # Send to current channel with view
        try:
            sent_message = await ctx.send(
                file=quote_file,
                view=view,
                reference=ctx.message,
                mention_author=False
            )
            
            # Store author info for tracking
            self.quote_authors[sent_message.id] = ctx.author.id
        except Exception as e:
            await ctx.send(f"❌ Failed to send quote: {e}", delete_after=5)
            return
        
        # Send to quotes channel if configured
        quotes_channel_id = await self.config.guild(ctx.guild).quotes_channel_id()
        if quotes_channel_id:
            try:
                quotes_channel = self.bot.get_channel(quotes_channel_id)
                if quotes_channel:
                    # Re-read the file since it was already sent
                    quote_image.seek(0)
                    quote_file_archive = discord.File(quote_image, filename="quote.png")
                    
                    # Create archive view with only jump button
                    archive_view = discord.ui.View(timeout=None)
                    archive_view.add_item(
                        discord.ui.Button(
                            label="Jump to original message",
                            style=discord.ButtonStyle.link,
                            url=message.jump_url
                        )
                    )
                    
                    # Send to archive
                    await quotes_channel.send(
                        file=quote_file_archive,
                        view=archive_view
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
