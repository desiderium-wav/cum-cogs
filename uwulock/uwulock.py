# uwulock.py
import discord
from redbot.core import commands, Config
from .uwuipy import uwuify
import asyncio

class uwulock(commands.Cog):
    """Locks a user into uwuified torment."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_global(uwulocked_user_ids=[])

    # ----------------------------
    # UwULock command
    # ----------------------------
    @commands.hybrid_command(name="uwulock", description="heh.", aliases=["uwu"])
    @commands.has_permissions(administrator=True)
    async def uwulock(self, ctx: commands.Context, member: discord.Member):
        uwulocked = await self.config.uwulocked_user_ids()
        if member.id in uwulocked:
            msg = await ctx.send(f"🔒 **{member.display_name}** is already uwulocked.")
        else:
            uwulocked.append(member.id)
            await self.config.uwulocked_user_ids.set(uwulocked)
            msg = await ctx.send(f"💖 **{member.display_name}** is now uwulocked. Prepare for suffering.")

        # Auto-delete the command and response
        await asyncio.sleep(0.5)
        try:
            await ctx.message.delete()
            await msg.delete()
        except discord.HTTPException:
            pass

    # ----------------------------
    # Unlock command
    # ----------------------------
    @commands.hybrid_command(name="unlock", description="Lift the curse.", aliases=["unuwu"])
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx: commands.Context, member: discord.Member):
        uwulocked = await self.config.uwulocked_user_ids()
        if member.id in uwulocked:
            uwulocked.remove(member.id)
            await self.config.uwulocked_user_ids.set(uwulocked)
            msg = await ctx.send(f"🔓 **{member.display_name}** has been released from their torment.")
        else:
            msg = await ctx.send(f"😇 **{member.display_name}** was not uwulocked.")

        # Auto-delete the command and response
        await asyncio.sleep(0.5)
        try:
            await ctx.message.delete()
            await msg.delete()
        except discord.HTTPException:
            pass

    # ----------------------------
    # Message listener: delete + uwuify repost
    # ----------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        uwulocked = await self.config.uwulocked_user_ids()
        if message.author.id in uwulocked:
            try:
                await message.delete()
                uwu_text = uwuify(message.content)

                webhook = None
                webhooks = await message.channel.webhooks()
                for wh in webhooks:
                    if wh.name == "UwULock":
                        webhook = wh
                        break
                if webhook is None:
                    webhook = await message.channel.create_webhook(name="UwULock")

                await webhook.send(
                    uwu_text,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

# ----------------------------
# Setup function (synchronous!)
# ----------------------------
def setup(bot):
    bot.add_cog(uwulock(bot))
