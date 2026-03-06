from .flash import Flash

async def setup(bot):
    """Load the Flash cog."""
    await bot.add_cog(Flash(bot))
