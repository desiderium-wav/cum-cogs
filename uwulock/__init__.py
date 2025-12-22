from .uwulock import Uwulock

async def setup(bot):
    await bot.add_cog(Uwulock(bot))
