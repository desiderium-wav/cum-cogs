import discord
from redbot.core import commands, bot
from redbot.core.utils.chat_formatting import bold
import os

# Stalk cog - handles startstalk and stopstalk commands with per-guild state

class Stalk(commands.Cog):
    """Commands for stalking and monitoring user messages."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        self.stalked_user_ids = {}  # Dict[guild_id, Set[user_id]]
        
        # Log channel for actions
        _raw_log_id = os.getenv("LOG_CHANNEL_ID")
        self.log_channel_id = int(_raw_log_id) if _raw_log_id and _raw_log_id.isdigit() else None
    
    def get_guild_state(self, guild_id: int) -> set:
        """Get or create the stalked users set for a guild."""
        if guild_id not in self.stalked_user_ids:
            self.stalked_user_ids[guild_id] = set()
        return self.stalked_user_ids[guild_id]
    
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
    
    @commands.hybrid_group(name="stalk", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    async def stalk_group(self, ctx: commands.Context, member: discord.Member = None):
        """Stalk commands. Use 'startstalk' to begin stalking."""
        if member:
            self.get_guild_state(ctx.guild.id).add(member.id)
            await ctx.send(f"Started stalking {member.mention}.")
        else:
            await ctx.send_help(ctx.command)
    
    @commands.hybrid_command(name="startstalk", description="Start stalking a user or all members")
    @commands.admin_or_permissions(administrator=True)
    async def startstalk(self, ctx: commands.Context, target: str = None, member: discord.Member = None):
        """Start stalking a user. Use 'all', 'server', or 'global' to stalk all members."""
        if target in ("all", "server", "global"):
            async def action(m):
                self.get_guild_state(ctx.guild.id).add(m.id)
            
            await ctx.defer()
            await self.apply_to_all_members(ctx, action, "Stalking")
            return
        
        if not member:
            await ctx.send("Specify a member or use `all`, `server`, or `global`.")
            return
        
        self.get_guild_state(ctx.guild.id).add(member.id)
        await ctx.send(f"Started stalking {member.mention}.")
    
    @commands.hybrid_command(name="stopstalk", description="Stop stalking a user or all members")
    @commands.admin_or_permissions(administrator=True)
    async def stopstalk(self, ctx: commands.Context, target: str = None, member: discord.Member = None):
        """Stop stalking a user. Use 'all', 'server', or 'global' to stop stalking all members."""
        if target in ("all", "server", "global"):
            async def action(m):
                self.get_guild_state(ctx.guild.id).discard(m.id)
            
            await ctx.defer()
            await self.apply_to_all_members(ctx, action, "Stopped stalking")
            return
        
        if not member:
            await ctx.send("Specify a member or use `all`, `server`, or `global`.")
            return
        
        self.get_guild_state(ctx.guild.id).discard(member.id)
        await ctx.send(f"Stopped stalking {member.mention}.")
    
    def is_stalked(self, user_id: int, guild_id: int) -> bool:
        """Check if a user is being stalked in a guild."""
        return user_id in self.get_guild_state(guild_id)

async def setup(bot: bot.Red):
    """Load the Stalk cog."""
    await bot.add_cog(Stalk(bot))
