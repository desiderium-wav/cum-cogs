import discord
from redbot.core import commands
from rembg import remove
from PIL import Image, ImageSequence
import io
import imageio
import numpy as np

class BgRemove(commands.Cog):
    """Remove backgrounds from images and GIFs."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bgremove")
    async def bgremove(self, ctx):
        """
        Remove the background from an attached image or GIF.
        """
        if not ctx.message.attachments:
            await ctx.send("Attach an image or GIF.")
            return

        attachment = ctx.message.attachments[0]
        filename = attachment.filename.lower()

        data = await attachment.read()

        if filename.endswith(".gif"):
            await ctx.send("Processing GIF… this may take a moment.")
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
        Remove background from a static image.
        """
        result = remove(data)
        buf = io.BytesIO(result)
        buf.seek(0)
        return buf

    async def _process_gif(self, data: bytes) -> io.BytesIO:
        """
        Remove background from each frame of a GIF and rebuild it.
        """
        gif = Image.open(io.BytesIO(data))
        frames = []
        durations = []

        for frame in ImageSequence.Iterator(gif):
            frame = frame.convert("RGBA")
            frame_bytes = io.BytesIO()
            frame.save(frame_bytes, format="PNG")
            processed = remove(frame_bytes.getvalue())
            processed_img = Image.open(io.BytesIO(processed)).convert("RGBA")

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
