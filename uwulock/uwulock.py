import discord
from redbot.core import commands, bot
from redbot.core.utils.chat_formatting import bold
import uwuipy
import os

# Uwulock cog - handles uwulock and unlock commands with per-guild state

class Uwulock(commands.Cog):
    """Commands for UWU-fying user messages."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        self.uwulocked_user_ids = {}  # Dict[guild_id, Set[user_id]]
        self.webhook_cache = {}  # Cache for webhooks per channel
        self.uwu = uwuipy.Uwuipy()
        
        # Log channel for actions
        _raw_log_id = os.getenv("LOG_CHANNEL_ID")
        self.log_channel_id = int(_raw_log_id) if _raw_log_id and _raw_log_id.isdigit() else None
    
    def get_guild_state(self, guild_id: int) -> set:
        """Get or create the UWU-locked users set for a guild."""
        if guild_id not in self.uwulocked_user_ids:
            self.uwulocked_user_ids[guild_id] = set()
        return self.uwulocked_user_ids[guild_id]
    
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
    
    async def apply_to_all_members(self, ctx: commands.Context, action, label: str):
        """Apply an action to all non-bot members in the guild."""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Administrator permission required.")
            return
        
        guild = ctx.guild
        count = 0
        
        print("Bulk helper invoked")
        print("Guild:", guild.name, guild.id)
        
        async for member in guild.fetch_members(limit=None):
            print("Found member:", member.id, member.bot)
            
            if member.bot:
                continue
            
            try:
                await action(member)
                count += 1
            except Exception as e:
                print("Action error:", e)
        
        print("Final count:", count)
        await ctx.send(f"{label} applied to {count} members.")
    
    @commands.hybrid_command(name="uwulock", description="UWU-fy a user's messages or all members")
    @commands.admin_or_permissions(administrator=True)
    async def uwulock(self, ctx: commands.Context, target: str = None, member: discord.Member = None):
        """Start UWU-fying a user's messages. Use 'all', 'server', or 'global' for all members."""
        if target in ("all", "server", "global"):
            async def action(m):
                self.get_guild_state(ctx.guild.id).add(m.id)
            
            await ctx.defer()
            await self.apply_to_all_members(ctx, action, "Uwulock")
            return
        
        if not member:
            await ctx.send("Specify a member or use `all`, `server`, or `global`.")
            return
        
        self.get_guild_state(ctx.guild.id).add(member.id)
        await ctx.send(f"{member.mention} has been uwulocked.")
    
    @commands.hybrid_command(name="unlock", description="Stop UWU-fying a user's messages or all members")
    @commands.admin_or_permissions(administrator=True)
    async def unlock(self, ctx: commands.Context, target: str = None, member: discord.Member = None):
        """Stop UWU-fying a user's messages. Use 'all', 'server', or 'global' for all members."""
        if target in ("all", "server", "global"):
            async def action(m):
                self.get_guild_state(ctx.guild.id).discard(m.id)
            
            await ctx.defer()
            await self.apply_to_all_members(ctx, action, "Unlock")
            return
        
        if not member:
            await ctx.send("Specify a member or use `all`, `server`, or `global`.")
            return
        
        self.get_guild_state(ctx.guild.id).discard(member.id)
        await ctx.send(f"{member.mention} has been unlocked.")
    
    def is_uwulocked(self, user_id: int, guild_id: int) -> bool:
        """Check if a user is UWU-locked in a guild."""
        return user_id in self.get_guild_state(guild_id)
    
    async def get_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        """Get or create a webhook for the channel."""
        if channel.id not in self.webhook_cache:
            webhooks = await channel.webhooks()
            webhook = discord.utils.get(webhooks, name="UwuFiend")
            if webhook is None:
                webhook = await channel.create_webhook(name="UwuFiend")
            self.webhook_cache[channel.id] = webhook
        return self.webhook_cache[channel.id]
    
    async def uwuify_message(self, message: discord.Message):
        """Convert a message to UWU speak via webhook."""
        try:
            await message.delete()
            
            channel = message.channel
            webhook = await self.get_webhook(channel)
            
            uwu_text = self.uwu.uwuify(message.content).strip()
            if len(uwu_text) > 2000:
                uwu_text = uwu_text[:1997] + "..."
            
            await webhook.send(
                content=uwu_text,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
        except Exception as e:
            print(f"[UWULOCK ERROR] Failed to uwuify message: {e}")
            await self.log_action(f"Failed to uwuify message from {message.author.display_name}: {e}")

async def setup(bot: bot.Red):
    """Load the Uwulock cog."""
    await bot.add_cog(Uwulock(bot))
