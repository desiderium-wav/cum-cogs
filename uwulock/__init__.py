from .uwulock import uwulock  # this must match the class name in uwulock.py

async def setup(bot):
    await bot.add_cog(uwulock(bot))
