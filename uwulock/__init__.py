from .uwulock import UwuLock

async def setup(bot):
    await bot.add_cog(UwuLock(bot))
