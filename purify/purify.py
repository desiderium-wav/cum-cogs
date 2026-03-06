import discord
from redbot.core import commands, bot, Config
from redbot.core.utils.chat_formatting import bold
import os
from io import BytesIO
import asyncio
from typing import Optional

# Purify cog - handles purify, startpurify, stoppurify, kill, and revive commands

class Purify(commands.Cog):
    """Admin management commands for message purification and bot control."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        self.kill_switch_engaged = False
        self.auto_purify_enabled = False
        self.purify_task = None
        
        # Config storage
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        self.config.register_guild(
            log_channel_id=None,
            purify_channel_ids=[]
        )
    
    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff")
    
    def message_has_image_attachment(self, msg: discord.Message) -> bool:
        """Check if message has image attachments."""
        if not msg.attachments:
            return False
        for att in msg.attachments:
            ctype = getattr(att, "content_type", None)
            if ctype and ctype.startswith("image"):
                return True
            if att.filename and att.filename.lower().endswith(self.IMAGE_EXTENSIONS):
                return True
        return False
    
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
        print(f"[PURIFY LOG - Guild {guild_id}] {message}")
    
    async def auto_purify_loop(self):
        """Background task for auto-purifying messages."""
        while not self.bot.is_closed():
            try:
                if self.auto_purify_enabled and not self.kill_switch_engaged:
                    # Get all guilds and iterate
                    for guild in self.bot.guilds:
                        purify_channel_ids = await self.config.guild(guild).purify_channel_ids()
                        for cid in purify_channel_ids:
                            channel = self.bot.get_channel(cid)
                            if not channel or not isinstance(channel, discord.TextChannel):
                                continue
                            try:
                                async for msg in channel.history(limit=None, oldest_first=True):
                                    if msg.author == self.bot.user:
                                        continue
                                    if self.message_has_image_attachment(msg):
                                        continue
                                    # Keep if reactions >= 3
                                    if msg.reactions and sum(r.count for r in msg.reactions) >= 3:
                                        continue
                                    try:
                                        await msg.delete()
                                        await self.log_action(
                                            guild.id,
                                            f"Auto-deleted message from {msg.author.display_name} in #{channel.name}"
                                        )
                                    except discord.HTTPException as e:
                                        await self.log_action(guild.id, f"Failed deleting message in #{channel.name}: {e}")
                                        await asyncio.sleep(1)
                            except Exception as e:
                                await self.log_action(
                                    guild.id,
                                    f"Error in auto-purify for #{channel.name if channel else cid}: {e}"
                                )
                # Sleep before next cycle (120 minutes)
                await asyncio.sleep(7200)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[PURIFY ERROR] Unexpected error in auto_purify_loop: {e}")
                await asyncio.sleep(60)
    
    @commands.hybrid_group(name="purifyconfig", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def purifyconfig(self, ctx: commands.Context):
        """Purify configuration settings."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        purify_channel_ids = await self.config.guild(ctx.guild).purify_channel_ids()
        
        log_channel_str = f"<#{log_channel_id}>" if log_channel_id else "Not set"
        purify_channels_str = ", ".join([f"<#{cid}>" for cid in purify_channel_ids]) if purify_channel_ids else "Not set"
        
        embed = discord.Embed(
            title="Purify Configuration",
            description="Current purify settings for this server",
            color=discord.Color.blue()
        )
        embed.add_field(name="Log Channel", value=log_channel_str, inline=False)
        embed.add_field(name="Purify Channels", value=purify_channels_str, inline=False)
        embed.add_field(
            name="Commands",
            value=(
                "`purifyconfig logchannel <channel>` - Set log channel\n"
                "`purifyconfig logchannel clear` - Clear log channel\n"
                "`purifyconfig addchannel <channel>` - Add purify channel\n"
                "`purifyconfig removechannel <channel>` - Remove purify channel\n"
                "`purifyconfig clearchannels` - Clear all purify channels"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @purifyconfig.group(name="logchannel", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def purifyconfig_logchannel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
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
    
    @purifyconfig_logchannel_group.command(name="clear", description="Clear the log channel")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def purifyconfig_logchannel_clear(self, ctx: commands.Context):
        """Clear the log channel setting."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        
        if not log_channel_id:
            await ctx.send("❌ No log channel is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).log_channel_id.clear()
        await ctx.send("✅ Log channel has been cleared.", delete_after=5)
    
    @purifyconfig.command(name="addchannel", description="Add a channel to the purify list")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def purifyconfig_addchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Add a channel to be purified."""
        purify_channel_ids = await self.config.guild(ctx.guild).purify_channel_ids()
        
        if channel.id in purify_channel_ids:
            await ctx.send(f"⚠️ {channel.mention} is already in the purify list.", delete_after=5)
            return
        
        purify_channel_ids.append(channel.id)
        await self.config.guild(ctx.guild).purify_channel_ids.set(purify_channel_ids)
        await ctx.send(f"✅ {channel.mention} added to purify channels.", delete_after=5)
    
    @purifyconfig.command(name="removechannel", description="Remove a channel from the purify list")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def purifyconfig_removechannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Remove a channel from being purified."""
        purify_channel_ids = await self.config.guild(ctx.guild).purify_channel_ids()
        
        if channel.id not in purify_channel_ids:
            await ctx.send(f"⚠️ {channel.mention} is not in the purify list.", delete_after=5)
            return
        
        purify_channel_ids.remove(channel.id)
        await self.config.guild(ctx.guild).purify_channel_ids.set(purify_channel_ids)
        await ctx.send(f"✅ {channel.mention} removed from purify channels.", delete_after=5)
    
    @purifyconfig.command(name="clearchannels", description="Clear all purify channels")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def purifyconfig_clearchannels(self, ctx: commands.Context):
        """Clear all purify channels."""
        await self.config.guild(ctx.guild).purify_channel_ids.clear()
        await ctx.send("✅ All purify channels have been cleared.", delete_after=5)
    
    @commands.hybrid_command(name="kill", description="Engage the kill switch to halt all bot activity")
    @commands.admin_or_permissions(administrator=True)
    async def kill(self, ctx: commands.Context):
        """Engage the kill switch to stop all bot activity."""
        self.kill_switch_engaged = True
        await ctx.send("☠️ Kill switch engaged. All bot activity halted.")
        await self.log_action(ctx.guild.id, "Kill switch was engaged.")
        try:
            await ctx.message.delete()
        except Exception:
            pass
    
    @commands.hybrid_command(name="revive", description="Disengage the kill switch to resume bot activity")
    @commands.admin_or_permissions(administrator=True)
    async def revive(self, ctx: commands.Context):
        """Disengage the kill switch to resume bot operations."""
        self.kill_switch_engaged = False
        await ctx.send("🩺 Kill switch disengaged. Bot is operational.")
        await self.log_action(ctx.guild.id, "Kill switch was disengaged.")
        try:
            await ctx.message.delete()
        except Exception:
            pass
    
    @commands.hybrid_command(name="purify", description="Manually trigger purification in current channel")
    @commands.admin_or_permissions(administrator=True)
    async def purify(self, ctx: commands.Context):
        """Manually trigger message purification in the current channel."""
        if self.kill_switch_engaged:
            await ctx.send("❌ Bot is currently in kill switch mode.", delete_after=5)
            return
        
        try:
            purify_channel_ids = await self.config.guild(ctx.guild).purify_channel_ids()
            deleted = 0
            if ctx.channel.id in purify_channel_ids:
                async for msg in ctx.channel.history(limit=None, oldest_first=True):
                    if msg.author == self.bot.user:
                        continue
                    if self.message_has_image_attachment(msg):
                        continue
                    if msg.reactions and sum(r.count for r in msg.reactions) >= 3:
                        continue
                    try:
                        await msg.delete()
                        deleted += 1
                    except discord.HTTPException as e:
                        await self.log_action(ctx.guild.id, f"Failed to delete message in purify: {e}")
                        await asyncio.sleep(1)
                await ctx.send(f"🧼 Purified {deleted} messages.", delete_after=5)
            else:
                await ctx.send("❌ This channel is not marked for purification.", delete_after=5)
        except Exception as e:
            await self.log_action(ctx.guild.id, f"Error in purify: {e}")
        
        try:
            await ctx.message.delete()
        except Exception:
            pass
    
    @commands.hybrid_command(name="startpurify", description="Begin the auto-purify cycle")
    @commands.admin_or_permissions(administrator=True)
    async def startpurify(self, ctx: commands.Context):
        """Start the automatic purification cycle."""
        if self.auto_purify_enabled:
            await ctx.send("🔄 Auto purify is already running.", delete_after=5)
            return
        
        self.auto_purify_enabled = True
        await self.log_action(ctx.guild.id, "Auto purify started.")
        await ctx.send("🔁 Auto purify is now running.", delete_after=5)
        
        try:
            await ctx.message.delete()
        except Exception:
            pass
    
    @commands.hybrid_command(name="stoppurify", description="Stop the auto-purify cycle")
    @commands.admin_or_permissions(administrator=True)
    async def stoppurify(self, ctx: commands.Context):
        """Stop the automatic purification cycle."""
        if not self.auto_purify_enabled:
            await ctx.send("⛔ Auto purify is not currently running.", delete_after=5)
            return
        
        self.auto_purify_enabled = False
        await self.log_action(ctx.guild.id, "Auto purify stopped.")
        await ctx.send("⛔ Auto purify has been stopped.", delete_after=5)
        
        try:
            await ctx.message.delete()
        except Exception:
            pass
    
    async def cog_load(self):
        """Start background tasks when cog loads."""
        if not self.purify_task or self.purify_task.done():
            self.purify_task = asyncio.create_task(self.auto_purify_loop())
    
    async def cog_unload(self):
        """Clean up background tasks when cog unloads."""
        if self.purify_task:
            self.purify_task.cancel()
            try:
                await self.purify_task
            except asyncio.CancelledError:
                pass

async def setup(bot: bot.Red):
    """Load the Purify cog."""
    await bot.add_cog(Purify(bot))
