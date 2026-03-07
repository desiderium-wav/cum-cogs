import discord
from redbot.core import commands, bot, Config
import asyncio
from typing import Optional
import os

# Flash cog - 5-minute flash message handler with auto-delete and spoiler enforcement

class Flash(commands.Cog):
    """5-minute flash message handler with auto-delete and media spoiler enforcement."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        
        # Per-message timers: {message_id: asyncio.Task}
        self.message_timers = {}
        
        # Webhook cache: {channel_id: webhook}
        self.webhook_cache = {}
        
        # Config storage
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(
            enabled=False,
            channel_id=None,
            role_id=None,
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
        print(f"[FLASH LOG - Guild {guild_id}] {message}")
    
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
            await self.log_action(channel.guild.id, f"Failed to create/get webhook in {channel.name}: {e}")
            return None
    
    async def repost_media_with_spoiler(self, message: discord.Message) -> Optional[discord.Message]:

        try:
            webhook = await self.get_webhook(message.channel)
            if not webhook:
                return None

            files = []

            for attachment in message.attachments:

                filename = attachment.filename.lower()

                if filename.endswith(".gif"):
                    continue

                try:
                    data = await attachment.read()

                    files.append(
                        discord.File(
                            fp=__import__("io").BytesIO(data),
                            filename=f"SPOILER_{attachment.filename}"
                        )
                    )

                except Exception as e:
                    await self.log_action(
                        message.guild.id,
                        f"Attachment read failed: {attachment.filename} ({e})"
                    )

            if not files:
                return None

            webhook_msg = await webhook.send(
                files=files,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                wait=True
            )

            return webhook_msg

        except Exception as e:
            await self.log_action(message.guild.id, f"Webhook repost failed: {e}")
            return None
    
    async def delete_message_after_timer(self, message: discord.Message, delay: int = 300):
        """Delete a message after the specified delay (default 5 minutes = 300 seconds)."""
        try:
            await asyncio.sleep(delay)
            await message.delete()
            if message.id in self.message_timers:
                del self.message_timers[message.id]
            await self.log_action(message.guild.id, f"Auto-deleted message {message.id} from {message.author.display_name}")
        except asyncio.CancelledError:
            pass
        except discord.NotFound:
            # Message was already deleted
            if message.id in self.message_timers:
                del self.message_timers[message.id]
        except Exception as e:
            await self.log_action(message.guild.id, f"Error deleting message {message.id}: {e}")
            if message.id in self.message_timers:
                del self.message_timers[message.id]
    
    async def handle_flash_message(self, message: discord.Message):

        # Ignore webhook messages so we don't repost them again
      if message.webhook_id is not None:
            task = asyncio.create_task(self.delete_message_after_timer(message))
            self.message_timers[message.id] = task
            return
          
        config = await self.config.guild(message.guild).all()

        is_media = self.message_has_image_or_video(message)

        # MEDIA HANDLING
        if is_media:

            reposted = await self.repost_media_with_spoiler(message)

            try:
                await message.delete()
            except Exception:
                pass

            if reposted:
                task = asyncio.create_task(self.delete_message_after_timer(reposted))
                self.message_timers[reposted.id] = task

            if config["role_id"]:
                role = message.guild.get_role(config["role_id"])
                if role:
                    try:
                        await message.channel.send(role.mention)
                    except Exception as e:
                        await self.log_action(message.guild.id, f"Role ping failed: {e}")

            return

        # NON MEDIA (text, bot, webhook, etc.)
        task = asyncio.create_task(self.delete_message_after_timer(message))
        self.message_timers[message.id] = task
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        config = await self.config.guild(message.guild).all()

        if not config["enabled"]:
            return

        if config["channel_id"] != message.channel.id:
            return

        await self.handle_flash_message(message)
    
    @commands.hybrid_group(name="flashset", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset(self, ctx: commands.Context):
        """Flash settings management. Use subcommands to configure."""
        config = await self.config.guild(ctx.guild).all()
        
        # Show current configuration
        enabled_status = "✅ Enabled" if config["enabled"] else "❌ Disabled"
        channel_str = f"<#{config['channel_id']}>" if config["channel_id"] else "Not set"
        role_str = f"<@&{config['role_id']}>" if config["role_id"] else "Not set"
        log_channel_str = f"<#{config['log_channel_id']}>" if config["log_channel_id"] else "Not set"
        
        embed = discord.Embed(
            title="Flash Configuration",
            description=f"Current settings for this server",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value=enabled_status, inline=False)
        embed.add_field(name="Flash Channel", value=channel_str, inline=False)
        embed.add_field(name="Ping Role", value=role_str, inline=False)
        embed.add_field(name="Log Channel", value=log_channel_str, inline=False)
        embed.add_field(
            name="Commands",
            value=(
                "`flashset enable` - Enable flash\n"
                "`flashset disable` - Disable flash\n"
                "`flashset channel <channel>` - Set flash channel\n"
                "`flashset channel clear` - Clear flash channel\n"
                "`flashset role <role>` - Set ping role\n"
                "`flashset role clear` - Clear ping role\n"
                "`flashset logchannel <channel>` - Set log channel\n"
                "`flashset logchannel clear` - Clear log channel\n"
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
        config = await self.config.guild(ctx.guild).all()
        
        if config["enabled"]:
            await ctx.send("⚠️ Flash is already enabled.", delete_after=5)
            return
        
        if not config["channel_id"]:
            await ctx.send("❌ Please set a flash channel first with `flashset channel <channel>`", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("✅ Flash has been enabled.", delete_after=5)
        await self.log_action(ctx.guild.id, f"Flash enabled in guild {ctx.guild.name}")
    
    @flashset.command(name="disable", description="Disable flash for this server")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_disable(self, ctx: commands.Context):
        """Disable flash for this server."""
        config = await self.config.guild(ctx.guild).all()
        
        if not config["enabled"]:
            await ctx.send("⚠️ Flash is already disabled.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("⛔ Flash has been disabled.", delete_after=5)
        await self.log_action(ctx.guild.id, f"Flash disabled in guild {ctx.guild.name}")
    
    @flashset.group(name="channel", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_channel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the flash channel."""
        config = await self.config.guild(ctx.guild).all()
        
        if channel is None:
            # Show current channel
            if config["channel_id"]:
                await ctx.send(f"Current flash channel: <#{config['channel_id']}>", delete_after=5)
            else:
                await ctx.send("No flash channel is set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"✅ Flash channel set to {channel.mention}", delete_after=5)
        await self.log_action(ctx.guild.id, f"Flash channel set to {channel.name}")
    
    @flashset_channel_group.command(name="clear", description="Clear the flash channel")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_channel_clear(self, ctx: commands.Context):
        """Clear the flash channel setting."""
        config = await self.config.guild(ctx.guild).all()
        
        if not config["channel_id"]:
            await ctx.send("❌ No flash channel is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).channel_id.clear()
        await ctx.send("✅ Flash channel has been cleared.", delete_after=5)
        await self.log_action(ctx.guild.id, f"Flash channel cleared")
    
    @flashset.group(name="role", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_role_group(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Set or view the ping role for image/video messages."""
        config = await self.config.guild(ctx.guild).all()
        
        if role is None:
            # Show current role
            if config["role_id"]:
                await ctx.send(f"Current ping role: <@&{config['role_id']}>", delete_after=5)
            else:
                await ctx.send("No ping role is set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).role_id.set(role.id)
        await ctx.send(f"✅ Ping role set to {role.mention}", delete_after=5)
        await self.log_action(ctx.guild.id, f"Flash ping role set to {role.name}")
    
    @flashset_role_group.command(name="clear", description="Clear the ping role")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_role_clear(self, ctx: commands.Context):
        """Clear the ping role setting."""
        config = await self.config.guild(ctx.guild).all()
        
        if not config["role_id"]:
            await ctx.send("❌ No ping role is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).role_id.clear()
        await ctx.send("✅ Ping role has been cleared.", delete_after=5)
        await self.log_action(ctx.guild.id, f"Flash ping role cleared")
    
    @flashset.group(name="logchannel", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_logchannel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the log channel."""
        config = await self.config.guild(ctx.guild).all()
        
        if channel is None:
            # Show current log channel
            if config["log_channel_id"]:
                await ctx.send(f"Current log channel: <#{config['log_channel_id']}>", delete_after=5)
            else:
                await ctx.send("No log channel is set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).log_channel_id.set(channel.id)
        await ctx.send(f"✅ Log channel set to {channel.mention}", delete_after=5)
    
    @flashset_logchannel_group.command(name="clear", description="Clear the log channel")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_logchannel_clear(self, ctx: commands.Context):
        """Clear the log channel setting."""
        config = await self.config.guild(ctx.guild).all()
        
        if not config["log_channel_id"]:
            await ctx.send("❌ No log channel is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).log_channel_id.clear()
        await ctx.send("✅ Log channel has been cleared.", delete_after=5)
    
    @flashset.command(name="clear", description="Clear all flash settings for this server")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def flashset_clear(self, ctx: commands.Context):
        """Clear all flash settings for this server."""
        await self.config.guild(ctx.guild).clear()
        await ctx.send("✅ All flash settings have been cleared.", delete_after=5)
        await self.log_action(ctx.guild.id, f"All flash settings cleared")
    
    async def cog_unload(self):
        """Cancel all pending message deletion tasks when cog unloads."""
        for task in self.message_timers.values():
            if not task.done():
                task.cancel()
        self.message_timers.clear()

async def setup(bot: bot.Red):
    """Load the Flash cog."""
    await bot.add_cog(Flash(bot))
