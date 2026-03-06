from .uwulock import Uwulock

async def setup(bot):
    """Load the Uwulock cog."""
    await bot.add_cog(Uwulock(bot))
