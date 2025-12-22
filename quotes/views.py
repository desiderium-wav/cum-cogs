import discord

class QuoteListView(discord.ui.View):
    def __init__(self, quotes):
        super().__init__(timeout=120)
        self.quotes = quotes
        self.page = 0
        self.per_page = 5

    def make_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_quotes = self.quotes[start:end]

        desc = "\n".join(
            f"#{q['number']} — {q['content'][:100]}"
            for q in page_quotes
        )

        embed = discord.Embed(description=desc)
        embed.set_footer(text=f"Page {self.page+1} of {(len(self.quotes)-1)//self.per_page+1}")
        return embed

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first(self, interaction, _):
        self.page = 0
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, _):
        self.page = (self.page - 1) % ((len(self.quotes)-1)//self.per_page+1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, _):
        self.page = (self.page + 1) % ((len(self.quotes)-1)//self.per_page+1)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last(self, interaction, _):
        self.page = (len(self.quotes)-1)//self.per_page
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.danger)
    async def close(self, interaction, _):
        await interaction.message.delete()


class ConfirmResetView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__()
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, _):
        await self.cog.config.guild(self.guild).clear()
        await interaction.message.delete()

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, _):
        await interaction.message.delete()


class RemoveQuoteView(discord.ui.View):
    def __init__(self, cog, guild, number):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.number = number

    @discord.ui.button(label="Remove Quote", style=discord.ButtonStyle.secondary)
    async def remove(self, interaction, _):
        quotes = await self.cog.config.guild(self.guild).quotes()
        quotes.pop(self.number - 1)
        for i, q in enumerate(quotes, start=1):
            q["number"] = i
        await self.cog.config.guild(self.guild).quotes.set(quotes)
        await interaction.message.delete()
