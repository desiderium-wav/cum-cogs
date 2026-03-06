from .quote import Quote

async def setup(bot):
    """Load the Quote cog."""
    await bot.add_cog(Quote(bot))
