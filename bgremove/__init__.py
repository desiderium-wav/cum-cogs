from .bgremove import BgRemove

async def setup(bot):
    await bot.add_cog(BgRemove(bot))
