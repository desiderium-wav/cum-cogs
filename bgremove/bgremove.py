import discord
from redbot.core import commands
from rembg import remove, new_session
from PIL import Image, ImageSequence
import io
import imageio
import numpy as np

class BgRemove(commands.Cog):
    """GPU-accelerated background removal with alpha matting."""

    def __init__(self, bot):
        self.bot = bot

        # Explicit ONNX session (GPU if available)
        self.session = new_session("u2net")

        # Alpha matting parameters (tuned for balance, not fantasy)
        self.remove_kwargs = {
            "session": self.session,
            "alpha_matting": True,
            "alpha_matting_foreground_threshold": 240,
            "alpha_matting_background_threshold": 10,
            "alpha_matting_erode_size": 10
        }

    @commands.command(name="bgremove")
    async def bgremove(self, ctx):
        """
        Remove the background from an attached image/GIF
        or from a replied-to message containing one.
        """
        attachment = None

        # Direct attachment
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]

        # Reply support
        elif ctx.message.reference:
            try:
                ref_msg = await ctx.channel.fetch_message(
                    ctx.message.reference.message_id
                )
                if ref_msg.attachments:
                    attachment = ref_msg.attachments[0]
            except discord.NotFound:
                pass

        if not attachment:
            await ctx.send("Attach or reply to an image or GIF.")
            return

        data = await attachment.read()
        filename = attachment.filename.lower()

        if filename.endswith(".gif"):
            await ctx.send("Processing GIF with alpha matting…")
            output = await self._process_gif(data)
            await ctx.send(
                file=discord.File(fp=output, filename="bgremoved.gif")
            )
        else:
            output = await self._process_image(data)
            await ctx.send(
                file=discord.File(fp=output, filename="bgremoved.png")
            )

    async def _process_image(self, data: bytes) -> io.BytesIO:
        """
        Background removal for static images.
        """
        result = remove(data, **self.remove_kwargs)
        buf = io.BytesIO(result)
        buf.seek(0)
        return buf

    async def _process_gif(self, data: bytes) -> io.BytesIO:
        """
        Frame-by-frame background removal for GIFs.
        """
        gif = Image.open(io.BytesIO(data))
        frames = []
        durations = []

        for frame in ImageSequence.Iterator(gif):
            frame = frame.convert("RGBA")

            frame_buf = io.BytesIO()
            frame.save(frame_buf, format="PNG")

            processed = remove(
                frame_buf.getvalue(),
                **self.remove_kwargs
            )

            processed_img = Image.open(
                io.BytesIO(processed)
            ).convert("RGBA")

            frames.append(np.array(processed_img))
            durations.append(frame.info.get("duration", 40))

        output = io.BytesIO()
        imageio.mimsave(
            output,
            frames,
            format="GIF",
            duration=[d / 1000 for d in durations],
            loop=0,
            disposal=2
        )
        output.seek(0)
        return output
