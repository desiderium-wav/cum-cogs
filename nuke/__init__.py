from .nuke import Nuke

async def setup(bot):
    """Load the Nuke cog."""
    await bot.add_cog(Nuke(bot))
