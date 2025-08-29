import io
import asyncio
from collections import OrderedDict
import discord
from redbot.core import commands, Config

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".mp4", ".mov", ".avi", ".mkv", ".webm"
}

class Flash(commands.Cog):
    """Five Minute Flash Handler for Red"""

    def __init__(self, bot):
        self.bot = bot
        self.batches = OrderedDict()
        # Config setup for channel and role IDs
        self.config = Config.get_conf(self, identifier=8745631)
        default_guild = {
            "flash_channel_id": None,
            "flash_ping_role_id": None,
        }
        self.config.register_guild(**default_guild)

    @staticmethod
    def is_media_attachment(attachment: discord.Attachment):
        filename = attachment.filename.lower()
        return any(filename.endswith(ext) for ext in MEDIA_EXTENSIONS)

    async def enforce_spoiler_with_webhook(self, message: discord.Message, media_attachments):
        all_spoilers = all(att.is_spoiler() for att in media_attachments)
        if all_spoilers:
            return message  # Already spoilered, do nothing

        channel = message.channel
        webhook = await channel.create_webhook(name="FlashSpoiler")

        try:
            files = []
            for attachment in media_attachments:
                file_bytes = await attachment.read()
                spoiler_filename = f"SPOILER_{attachment.filename}" if not attachment.is_spoiler() else attachment.filename
                files.append(discord.File(io.BytesIO(file_bytes), filename=spoiler_filename))

            await message.delete()
            await webhook.send(
                content=message.content or None,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                files=files
            )

            history = [m async for m in channel.history(limit=1)]
            return history[0] if history else None

        finally:
            await webhook.delete()

    async def start_flash_timer(self, batch_id: int):
        await asyncio.sleep(300)
        batch = self.batches.pop(batch_id, None)
        if not batch:
            return

        try:
            await batch["start_message"].channel.delete_messages(batch["messages"])
        except discord.HTTPException:
            for msg in batch["messages"]:
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ Flash cog loaded as {self.bot.user}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Avoid recursion/other bots
        if message.author.bot:
            return
        guild = message.guild
        if not guild:
            return

        flash_channel_id = await self.config.guild(guild).flash_channel_id()
        flash_ping_role_id = await self.config.guild(guild).flash_ping_role_id()
        if not flash_channel_id or not flash_ping_role_id:
            return

        if message.channel.id != flash_channel_id:
            return

        media_attachments = [att for att in message.attachments if self.is_media_attachment(att)]

        if media_attachments:
            new_message = await self.enforce_spoiler_with_webhook(message, media_attachments)
            if not new_message:
                return

            flash_ping_role = message.guild.get_role(flash_ping_role_id)
            ping_message = None
            if flash_ping_role:
               ping_message = await message.channel.send(
                    f"<@&{flash_ping_role.id}>",
                    allowed_mentions=discord.AllowedMentions(roles=[flash_ping_role])
                )

            batch_id = new_message.id
            self.batches[batch_id] = {
                "start_message": new_message,
                "messages": [new_message],
            }
            if ping_message:
                self.batches[batch_id]["messages"].append(ping_message)
            self.bot.loop.create_task(self.start_flash_timer(batch_id))
        else:
            if not self.batches:
                await message.delete()
            else:
                latest_batch_id = next(reversed(self.batches))
                self.batches[latest_batch_id]["messages"].append(message)

    @commands.command(name="showbatches")
    @commands.admin_or_permissions(administrator=True)
    async def show_batches(self, ctx):
        """Show active flash batches."""
        if not self.batches:
            await ctx.send("📭 No active batches.")
            return
        msg_lines = []
        for idx, (batch_id, batch_data) in enumerate(self.batches.items(), start=1):
            msg_lines.append(
                f"**Batch {idx}**\n"
                f"- Start message ID: `{batch_id}`\n"
                f"- Messages in batch: `{len(batch_data['messages'])}`"
            )
        await ctx.send("\n\n".join(msg_lines))

    @commands.group()
    @commands.admin_or_permissions(administrator=True)
    async def flashset(self, ctx):
        """Settings for Flash."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @flashset.command(name="channel")
    async def flashset_channel(self, ctx, channel: discord.TextChannel):
        """Set the flash channel."""
        await self.config.guild(ctx.guild).flash_channel_id.set(channel.id)
        await ctx.send(f"Flash channel set to {channel.mention}")

    @flashset.command(name="role")
    async def flashset_role(self, ctx, role: discord.Role):
        """Set the flash ping role."""
        await self.config.guild(ctx.guild).flash_ping_role_id.set(role.id)
        await ctx.send(f"Flash ping role set to {role.mention}")

def setup(bot):
    bot.add_cog(Flash(bot))
