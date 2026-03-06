import discord
from redbot.core import commands, bot
from redbot.core.utils.chat_formatting import bold

# Nuke cog - server reset command for bot owner only

class Nuke(commands.Cog):
    """Owner-only dangerous commands."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
    
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
        
        try:
            await ctx.message.delete()
        except Exception:
            pass

async def setup(bot: bot.Red):
    """Load the Nuke cog."""
    await bot.add_cog(Nuke(bot))
