from .stalk import Stalk

async def setup(bot):
    """Load the Stalk cog."""
    await bot.add_cog(Stalk(bot))
