from .purify import Purify

async def setup(bot):
    """Load the Purify cog."""
    await bot.add_cog(Purify(bot))
