from .flash import Flash

async def setup(bot):
    await bot.add_cog(Flash(bot))
