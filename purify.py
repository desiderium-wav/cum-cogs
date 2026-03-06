import discord
from redbot.core import commands, bot
from redbot.core.utils.chat_formatting import bold
import os
from io import BytesIO
import asyncio

# Purify cog - handles purify, startpurify, stoppurify, kill, and revive commands

class Purify(commands.Cog):
    """Admin management commands for message purification and bot control."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        self.kill_switch_engaged = False
        self.auto_purify_enabled = False
        self.purify_task = None
        
        # Load purify channel IDs from environment
        raw_channel_ids = os.getenv("PURIFY_CHANNEL_IDS", "")
        self.PURIFY_CHANNEL_IDS = {int(cid.strip()) for cid in raw_channel_ids.split(",") if cid.strip().isdigit()}
        
        # Log channel for actions
        _raw_log_id = os.getenv("LOG_CHANNEL_ID")
        self.log_channel_id = int(_raw_log_id) if _raw_log_id and _raw_log_id.isdigit() else None
    
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
    
    async def log_action(self, message: str):
        """Log an action to the log channel if configured."""
        if self.log_channel_id:
            try:
                log_channel = self.bot.get_channel(self.log_channel_id)
                if log_channel:
                    await log_channel.send(message)
            except Exception:
                pass
        print(f"[LOG] {message}")
    
    async def auto_purify_loop(self):
        """Background task for auto-purifying messages."""
        while not self.bot.is_closed():
            try:
                if self.auto_purify_enabled and not self.kill_switch_engaged:
                    for cid in self.PURIFY_CHANNEL_IDS:
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
                                        f"Auto-deleted message from {msg.author.display_name} in #{channel.name}"
                                    )
                                except discord.HTTPException as e:
                                    await self.log_action(f"Failed deleting message in #{channel.name}: {e}")
                                    await asyncio.sleep(1)
                        except Exception as e:
                            await self.log_action(
                                f"Error in auto-purify for #{channel.name if channel else cid}: {e}"
                            )
                # Sleep before next cycle (120 minutes)
                await asyncio.sleep(7200)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.log_action(f"Unexpected error in auto_purify_loop: {e}")
                await asyncio.sleep(60)
    
    @commands.hybrid_command(name="kill", description="Engage the kill switch to halt all bot activity")
    @commands.admin_or_permissions(administrator=True)
    async def kill(self, ctx: commands.Context):
        """Engage the kill switch to stop all bot activity."""
        self.kill_switch_engaged = True
        await ctx.send("☠️ Kill switch engaged. All bot activity halted.")
        await self.log_action("Kill switch was engaged.")
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
        await self.log_action("Kill switch was disengaged.")
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
            deleted = 0
            if ctx.channel.id in self.PURIFY_CHANNEL_IDS:
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
                        await self.log_action(f"Failed to delete message in purify: {e}")
                        await asyncio.sleep(1)
                await ctx.send(f"🧼 Purified {deleted} messages.", delete_after=5)
            else:
                await ctx.send("❌ This channel is not marked for purification.", delete_after=5)
        except Exception as e:
            await self.log_action(f"Error in purify: {e}")
        
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
        await self.log_action("Auto purify started.")
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
        await self.log_action("Auto purify stopped.")
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
