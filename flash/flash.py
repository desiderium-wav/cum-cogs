import discord
from redbot.core import commands, bot
import asyncio
from typing import Optional, Dict, Set
import os

# Flash cog - 5-minute flash message handler with auto-delete and spoiler enforcement

class Flash(commands.Cog):
    """5-minute flash message handler with auto-delete and media spoiler enforcement."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        
        # Per-guild configuration: {guild_id: {"enabled": bool, "channel_id": int, "role_id": int}}
        self.flash_config = {}
        
        # Per-message timers: {message_id: asyncio.Task}
        self.message_timers = {}
        
        # Webhook cache: {channel_id: webhook}
        self.webhook_cache = {}
        
        # Log channel for actions
        _raw_log_id = os.getenv("LOG_CHANNEL_ID")
        self.log_channel_id = int(_raw_log_id) if _raw_log_id and _raw_log_id.isdigit() else None
    
    def get_guild_config(self, guild_id: int) -> dict:
        """Get or create configuration for a guild."""
        if guild_id not in self.flash_config:
            self.flash_config[guild_id] = {
                "enabled": False,
                "channel_id": None,
                "role_id": None
            }
        return self.flash_config[guild_id]
    
    async def log_action(self, message: str):
        """Log an action to the log channel if configured."""
        if self.log_channel_id:
            try:
                log_channel = self.bot.get_channel(self.log_channel_id)
                if log_channel:
                    await log_channel.send(message)
            except Exception:
                pass
        print(f"[FLASH LOG] {message}")
    
    def message_has_image_or_video(self, msg: discord.Message) -> bool:
        """Check if message has image or video attachments (excluding gifs, stickers, emojis)."""
        if not msg.attachments:
            return False
        
        image_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
        video_extensions = (".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".wmv")
        excluded_extensions = (".gif",)
        
        for att in msg.attachments:
            filename = att.filename.lower() if att.filename else ""
            content_type = getattr(att, "content_type", "").lower()
            
            # Check by content type first
            if content_type.startswith("image") or content_type.startswith("video"):
                # Exclude gifs
                if filename.endswith(excluded_extensions):
                    continue
                if content_type == "image/gif":
                    continue
                return True
            
            # Check by extension
            if filename.endswith(image_extensions) or filename.endswith(video_extensions):
                return True
        
        return False
    
    async def get_webhook(self, channel: discord.TextChannel) -> Optional[discord.Webhook]:
        """Get or create a webhook for the channel."""
        try:
            if channel.id not in self.webhook_cache:
                webhooks = await channel.webhooks()
                webhook = discord.utils.get(webhooks, name="FlashHandler")
                if webhook is None:
                    webhook = await channel.create_webhook(name="FlashHandler")
                self.webhook_cache[channel.id] = webhook
            return self.webhook_cache[channel.id]
        except Exception as e:
            await self.log_action(f"Failed to create/get webhook in {channel.name}: {e}")
            return None
    
    async def repost_media_with_spoiler(self, message: discord.Message):
        """Repost message media with spoiler tags via webhook."""
        try:
            channel = message.channel
            webhook = await self.get_webhook(channel)
            
            if not webhook:
                return
            
            # Prepare files with spoiler flag
            files = []
            for attachment in message.attachments:
                # Only repost images and videos (excluding gifs)
                if not self.message_has_image_or_video(message):
                    continue
                
                filename = attachment.filename.lower() if attachment.filename else ""
                if filename.endswith((".gif",)):
                    continue
                
                try:
                    file_data = await attachment.read()
                    # Add SPOILER_ prefix to filename to apply spoiler tag
                    spoiler_filename = f"SPOILER_{attachment.filename}"
                    files.append(discord.File(
                        fp=__import__('io').BytesIO(file_data),
                        filename=spoiler_filename
                    ))
                except Exception as e:
                    await self.log_action(f"Failed to read attachment {attachment.filename}: {e}")
            
            if files:
                await webhook.send(
                    files=files,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                )
        except Exception as e:
            await self.log_action(f"Failed to repost media with spoiler: {e}")
    
    async def delete_message_after_timer(self, message: discord.Message, delay: int = 300):
        """Delete a message after the specified delay (default 5 minutes = 300 seconds)."""
        try:
            await asyncio.sleep(delay)
            await message.delete()
            if message.id in self.message_timers:
                del self.message_timers[message.id]
            await self.log_action(f"Auto-deleted message {message.id} from {message.author.display_name}")
        except asyncio.CancelledError:
            pass
        except discord.NotFound:
            # Message was already deleted
            if message.id in self.message_timers:
                del self.message_timers[message.id]
        except Exception as e:
            await self.log_action(f"Error deleting message {message.id}: {e}")
            if message.id in self.message_timers:
                del self.message_timers[message.id]
    
    async def handle_flash_message(self, message: discord.Message):
        """Handle a message in the flash channel."""
        config = self.get_guild_config(message.guild.id)
        
        # Check if flash is enabled and this is the flash channel
        if not config["enabled"] or config["channel_id"] != message.channel.id:
            return
        
        # Skip bot messages
        if message.author.bot:
            return
        
        # Check if this is an image or video message
        is_image_or_video = self.message_has_image_or_video(message)
        
        if is_image_or_video:
            # Repost media with spoiler
            await self.repost_media_with_spoiler(message)
            
            # Ping the role if one is configured
            if config["role_id"]:
                try:
                    role = message.guild.get_role(config["role_id"])
                    if role:
                        await message.reply(f"{role.mention}", mention_author=False)
                except Exception as e:
                    await self.log_action(f"Failed to ping role: {e}")
        
        # Create timer for message deletion
        task = asyncio.create_task(self.delete_message_after_timer(message))
        self.message_timers[message.id] = task
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages in flash channels."""
        if message.guild is None:
            return
        
        config = self.get_guild_config(message.guild.id)
        
        # Check if flash is enabled and this is the flash channel
        if config["enabled"] and config["channel_id"] == message.channel.id:
            await self.handle_flash_message(message)
    
    @commands.hybrid_group(name="flashset", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset(self, ctx: commands.Context):
        """Flash settings management. Use subcommands to configure."""
        config = self.get_guild_config(ctx.guild.id)
        
        # Show current configuration
        enabled_status = "✅ Enabled" if config["enabled"] else "❌ Disabled"
        channel_str = f"<#{config['channel_id']}>" if config["channel_id"] else "Not set"
        role_str = f"<@&{config['role_id']}>" if config["role_id"] else "Not set"
        
        embed = discord.Embed(
            title="Flash Configuration",
            description=f"Current settings for this server",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value=enabled_status, inline=False)
        embed.add_field(name="Flash Channel", value=channel_str, inline=False)
        embed.add_field(name="Ping Role", value=role_str, inline=False)
        embed.add_field(
            name="Commands",
            value=(
                "`flashset enable` - Enable flash\n"
                "`flashset disable` - Disable flash\n"
                "`flashset channel <channel>` - Set flash channel\n"
                "`flashset channel clear` - Clear flash channel\n"
                "`flashset role <role>` - Set ping role\n"
                "`flashset role clear` - Clear ping role\n"
                "`flashset clear` - Clear all settings"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @flashset.command(name="enable", description="Enable flash for this server")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_enable(self, ctx: commands.Context):
        """Enable flash for this server."""
        config = self.get_guild_config(ctx.guild.id)
        
        if config["enabled"]:
            await ctx.send("⚠️ Flash is already enabled.", delete_after=5)
            return
        
        if not config["channel_id"]:
            await ctx.send("❌ Please set a flash channel first with `flashset channel <channel>`", delete_after=5)
            return
        
        config["enabled"] = True
        await ctx.send("✅ Flash has been enabled.", delete_after=5)
        await self.log_action(f"Flash enabled in guild {ctx.guild.name} ({ctx.guild.id})")
    
    @flashset.command(name="disable", description="Disable flash for this server")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_disable(self, ctx: commands.Context):
        """Disable flash for this server."""
        config = self.get_guild_config(ctx.guild.id)
        
        if not config["enabled"]:
            await ctx.send("⚠️ Flash is already disabled.", delete_after=5)
            return
        
        config["enabled"] = False
        await ctx.send("⛔ Flash has been disabled.", delete_after=5)
        await self.log_action(f"Flash disabled in guild {ctx.guild.name} ({ctx.guild.id})")
    
    @flashset.group(name="channel", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_channel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the flash channel."""
        if channel is None:
            # Show current channel
            config = self.get_guild_config(ctx.guild.id)
            if config["channel_id"]:
                await ctx.send(f"Current flash channel: <#{config['channel_id']}>", delete_after=5)
            else:
                await ctx.send("No flash channel is set.", delete_after=5)
            return
        
        config = self.get_guild_config(ctx.guild.id)
        config["channel_id"] = channel.id
        await ctx.send(f"✅ Flash channel set to {channel.mention}", delete_after=5)
        await self.log_action(f"Flash channel set to {channel.name} in guild {ctx.guild.name}")
    
    @flashset_channel_group.command(name="clear", description="Clear the flash channel")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_channel_clear(self, ctx: commands.Context):
        """Clear the flash channel setting."""
        config = self.get_guild_config(ctx.guild.id)
        
        if not config["channel_id"]:
            await ctx.send("❌ No flash channel is currently set.", delete_after=5)
            return
        
        config["channel_id"] = None
        await ctx.send("✅ Flash channel has been cleared.", delete_after=5)
        await self.log_action(f"Flash channel cleared in guild {ctx.guild.name}")
    
    @flashset.group(name="role", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_role_group(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Set or view the ping role for image/video messages."""
        if role is None:
            # Show current role
            config = self.get_guild_config(ctx.guild.id)
            if config["role_id"]:
                await ctx.send(f"Current ping role: <@&{config['role_id']}>", delete_after=5)
            else:
                await ctx.send("No ping role is set.", delete_after=5)
            return
        
        config = self.get_guild_config(ctx.guild.id)
        config["role_id"] = role.id
        await ctx.send(f"✅ Ping role set to {role.mention}", delete_after=5)
        await self.log_action(f"Flash ping role set to {role.name} in guild {ctx.guild.name}")
    
    @flashset_role_group.command(name="clear", description="Clear the ping role")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_role_clear(self, ctx: commands.Context):
        """Clear the ping role setting."""
        config = self.get_guild_config(ctx.guild.id)
        
        if not config["role_id"]:
            await ctx.send("❌ No ping role is currently set.", delete_after=5)
            return
        
        config["role_id"] = None
        await ctx.send("✅ Ping role has been cleared.", delete_after=5)
        await self.log_action(f"Flash ping role cleared in guild {ctx.guild.name}")
    
    @flashset.command(name="clear", description="Clear all flash settings for this server")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_clear(self, ctx: commands.Context):
        """Clear all flash settings for this server."""
        if ctx.guild.id in self.flash_config:
            del self.flash_config[ctx.guild.id]
        
        await ctx.send("✅ All flash settings have been cleared.", delete_after=5)
        await self.log_action(f"All flash settings cleared in guild {ctx.guild.name}")
    
    async def cog_unload(self):
        """Cancel all pending message deletion tasks when cog unloads."""
        for task in self.message_timers.values():
            if not task.done():
                task.cancel()
        self.message_timers.clear()

async def setup(bot: bot.Red):
    """Load the Flash cog."""
    await bot.add_cog(Flash(bot))
