import discord
from redbot.core import commands, bot, Config
from redbot.core.utils.chat_formatting import bold
import uwuipy
from typing import Optional
from typing import Union
from discord import app_commands

# Uwulock cog - handles uwulock and unlock commands with per-guild state

class Uwulock(commands.Cog):
    """Commands for UWU-fying user messages."""
    
    def __init__(self, bot: bot.Red):
        self.bot = bot
        self.uwulocked_user_ids = {}  # Dict[guild_id, Set[user_id]]
        self.webhook_cache = {}  # Cache for webhooks per channel
        self.uwu = uwuipy.Uwuipy()
        
        # Config storage
        self.config = Config.get_conf(self, identifier=1234567892, force_registration=True)
        self.config.register_guild(
            log_channel_id=None
        )
    
    def get_guild_state(self, guild_id: int) -> set:
        """Get or create the UWU-locked users set for a guild."""
        if guild_id not in self.uwulocked_user_ids:
            self.uwulocked_user_ids[guild_id] = set()
        return self.uwulocked_user_ids[guild_id]
    
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
        print(f"[UWULOCK LOG - Guild {guild_id}] {message}")
    
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
    
    @commands.hybrid_group(name="uwulockcfg", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def uwulockcfg(self, ctx: commands.Context):
        """Uwulock configuration settings."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        
        log_channel_str = f"<#{log_channel_id}>" if log_channel_id else "Not set"
        
        embed = discord.Embed(
            title="Uwulock Configuration",
            description="Current uwulock settings for this server",
            color=discord.Color.blue()
        )
        embed.add_field(name="Log Channel", value=log_channel_str, inline=False)
        embed.add_field(
            name="Commands",
            value=(
                "`uwulockcfg logchannel <channel>` - Set log channel\n"
                "`uwulockcfg logchannel clear` - Clear log channel\n"
                "`uwulock <member|all>` - UWU-lock user(s)\n"
                "`unlock <member|all>` - Unlock user(s)"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @uwulockcfg.group(name="logchannel", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def uwulockcfg_logchannel_group(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
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
    
    @uwulockcfg_logchannel_group.command(name="clear", description="Clear the log channel")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def uwulockcfg_logchannel_clear(self, ctx: commands.Context):
        """Clear the log channel setting."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel_id()
        
        if not log_channel_id:
            await ctx.send("❌ No log channel is currently set.", delete_after=5)
            return
        
        await self.config.guild(ctx.guild).log_channel_id.clear()
        await ctx.send("✅ Log channel has been cleared.", delete_after=5)
    
    @commands.hybrid_command(name="uwulock", description="UWU-fy a user's messages or all members")
    @app_commands.describe(target="User to uwulock or a scope option")
    @app_commands.choices(target=[
        app_commands.Choice(name="All Members", value="all"),
        app_commands.Choice(name="Server", value="server"),
        app_commands.Choice(name="Global", value="global"),
    ])
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def uwulock(self, ctx: commands.Context, target: Union[discord.Member, str]):
        """Start UWU-fying a user's messages."""

        if isinstance(target, str) and target.lower() in ("all", "server", "global"):
            async def action(m):
                self.get_guild_state(ctx.guild.id).add(m.id)

            await ctx.defer()
            await self.apply_to_all_members(ctx, action, "Uwulock")
            return

        if isinstance(target, discord.Member):
            self.get_guild_state(ctx.guild.id).add(target.id)
            await ctx.send(f"{target.mention} has been uwulocked.")
    
    @commands.hybrid_command(name="unlock", description="Stop UWU-fying a user's messages or all members")
    @app_commands.describe(target="User to unlock or a scope option")
    @app_commands.choices(target=[
        app_commands.Choice(name="All Members", value="all"),
        app_commands.Choice(name="Server", value="server"),
        app_commands.Choice(name="Global", value="global"),
    ])
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    async def unlock(self, ctx: commands.Context, target: Union[discord.Member, str]):
        """Stop UWU-fying a user's messages."""

        if isinstance(target, str) and target.lower() in ("all", "server", "global"):
            async def action(m):
                self.get_guild_state(ctx.guild.id).discard(m.id)

            await ctx.defer()
            await self.apply_to_all_members(ctx, action, "Unlock")
            return

        if isinstance(target, discord.Member):
            self.get_guild_state(ctx.guild.id).discard(target.id)
            await ctx.send(f"{target.mention} has been unlocked.")
    
    def is_uwulocked(self, user_id: int, guild_id: int) -> bool:
        """Check if a user is UWU-locked in a guild."""
        return user_id in self.get_guild_state(guild_id)
    
    async def get_webhook(self, channel: discord.TextChannel) -> Optional[discord.Webhook]:
        """Get or create a webhook for the channel."""
        try:
            if channel.id not in self.webhook_cache:
                webhooks = await channel.webhooks()
                webhook = discord.utils.get(webhooks, name="UwuFiend")
                if webhook is None:
                    webhook = await channel.create_webhook(name="UwuFiend")
                self.webhook_cache[channel.id] = webhook
            return self.webhook_cache[channel.id]
        except Exception as e:
            await self.log_action(channel.guild.id, f"Failed to create/get webhook in {channel.name}: {e}")
            return None
    
    async def uwuify_message(self, message: discord.Message):
        """Convert a message to UWU speak via webhook."""
        try:
            await message.delete()
            
            channel = message.channel
            webhook = await self.get_webhook(channel)
            
            if not webhook:
                return
            
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
            await self.log_action(message.guild.id, f"Failed to uwuify message from {message.author.display_name}: {e}")

async def setup(bot: bot.Red):
    """Load the Uwulock cog."""
    await bot.add_cog(Uwulock(bot))
