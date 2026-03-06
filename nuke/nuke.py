import discord
from redbot.core import commands, bot, Config
from typing import Optional

# Nuke cog - server reset command for bot owner only

class Nuke(commands.Cog):
    """Owner-only dangerous commands."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        
        # Config storage
        self.config = Config.get_conf(self, identifier=1234567894, force_registration=True)
        self.config.register_guild(
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
        print(f"[NUKE LOG - Guild {guild_id}] {message}")
    
    @commands.hybrid_group(name="nukecfg", invoke_without_command=True)
    @commands.is_owner()
    @commands.guild_only()
    async def nukecfg(self, ctx: commands.Context):
        """Nuke configuration settings (owner only)."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        
        log_channel_str = f"<#{log_channel_id}>" if log_channel_id else "Not set"
        
        embed = discord.Embed(
            title="Nuke Configuration",
            description="Current nuke settings for this server",
            color=discord.Color.red()
        )
        embed.add_field(name="Log Channel", value=log_channel_str, inline=False)
        embed.add_field(
            name="Commands",
            value=(
                "`nukecfg logchannel <channel>` - Set log channel\n"
                "`nukecfg logchannel clear` - Clear log channel\n"
                "`nuke` - Nuke the server (requires confirmation)"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @nukecfg.group(name="logchannel", invoke_without_command=True)
    @commands.is_owner()
    @commands.guild_only()
    async def nukecfg_logchannel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
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
    
    @nukecfg_logchannel_group.command(name="clear", description="Clear the log channel")
    @commands.is_owner()
    @commands.guild_only()
    async def nukecfg_logchannel_clear(self, ctx: commands.Context):
        """Clear the log channel setting."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        
        if not log_channel_id:
            await ctx.send("❌ No log channel is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).log_channel_id.clear()
        await ctx.send("✅ Log channel has been cleared.", delete_after=5)
    
    @commands.command(name="nuke", description="Reset the server while preserving admin roles and members")
    @commands.is_owner()
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def nuke(self, ctx: commands.Context):
        """
        Reset the server while preserving admin roles and members.
        Bot owner only.
        """
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("❌ This command is only available to the bot owner.", delete_after=5)
            return
        
        guild = ctx.guild
        if guild is None:
            return
        
        await ctx.send(
            "⚠️ **WARNING**: You are about to nuke this server. "
            "This will delete all channels and non-admin roles. "
            "React with ✅ within 30 seconds to confirm.",
            delete_after=30
        )
        
        try:
            reaction, user = await self.bot.wait_for(
                "reaction_add",
                timeout=30.0,
                check=lambda r, u: u == ctx.author and r.emoji == "✅"
            )
        except Exception:
            await ctx.send("❌ Nuke cancelled.", delete_after=5)
            return
        
        # Delete all channels
        for channel in list(guild.channels):
            try:
                await channel.delete(reason="Server reset command invoked by bot owner.")
            except Exception as e:
                print(f"Failed to delete channel {channel.name}: {e}")
        
        # Delete non-admin roles (skip @everyone and admin roles)
        for role in list(guild.roles):
            if role.is_default():
                continue
            if role.permissions.administrator:
                continue
            try:
                await role.delete(reason="Server reset command invoked by bot owner.")
            except Exception as e:
                print(f"Failed to delete role {role.name}: {e}")
        
        # Rename the guild
        try:
            await guild.edit(name="oops, wrong button", reason="Server reset command invoked by bot owner.")
        except Exception as e:
            print(f"Failed to rename guild: {e}")
        
        # Create the comedic channel
        try:
            await guild.create_text_channel("my bad y'all", reason="Server reset command invoked by bot owner.")
        except Exception as e:
            print(f"Failed to create channel: {e}")
        
        await self.log_action(guild.id, "Server was nuked by bot owner.")
        
        try:
            await ctx.message.delete()
        except Exception:
            pass

async def setup(bot: bot.Red):
    """Load the Nuke cog."""
    await bot.add_cog(Nuke(bot))
