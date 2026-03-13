import discord
import re
import time
import tempfile
from pathlib import Path
from rapidfuzz import fuzz

import whisper

from redbot.core import commands, Config, bank
from redbot.core.utils.chat_formatting import humanize_number


class SwearJar(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=92837423)

        default_guild = {
            "enabled": True,
            "jar_balance": 0,
            "fine_amount": 10,
            "cooldown": 10,
            "jackpot_threshold": 10000
        }

        default_user = {
            "swear_count": 0,
            "last_trigger": 0
        }

        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)

        self.badwords = self.load_badwords()

        self.whisper_model = whisper.load_model("base")

    # ----------------------------
    # Load bad words
    # ----------------------------

    def load_badwords(self):
        path = Path(__file__).parent / "badwords.txt"

        with open(path) as f:
            return [w.strip().lower() for w in f if w.strip()]

    # ----------------------------
    # Regex expansion detection
    # ----------------------------

    def regex_detect(self, text):

        count = 0

        for word in self.badwords:

            pattern = word.replace("i", "[i1!]").replace("o", "[o0]").replace("a", "[a@]")

            matches = re.findall(pattern, text)

            count += len(matches)

        return count

    # ----------------------------
    # Phonetic / fuzzy detection
    # ----------------------------

    def phonetic_detect(self, text):

        words = text.split()

        matches = 0

        for w in words:
            for bad in self.badwords:

                score = fuzz.ratio(w, bad)

                if score > 85:
                    matches += 1

        return matches

    # ----------------------------
    # Context filter
    # ----------------------------

    def context_filter(self, text):

        allowed_contexts = [
            "swear word list",
            "example swear",
            "dictionary",
            "quote"
        ]

        for ctx in allowed_contexts:
            if ctx in text:
                return False

        return True

    # ----------------------------
    # Speech transcription
    # ----------------------------

    async def transcribe(self, attachment):

        with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:

            await attachment.save(tmp.name)

            result = self.whisper_model.transcribe(tmp.name)

            return result["text"]

    # ----------------------------
    # Core swear detection
    # ----------------------------

    def detect_swears(self, text):

        text = text.lower()

        if not self.context_filter(text):
            return 0

        count = 0

        for word in self.badwords:

            count += len(re.findall(rf"\b{re.escape(word)}\b", text))

        count += self.regex_detect(text)

        count += self.phonetic_detect(text)

        return count

    # ----------------------------
    # Cooldown system
    # ----------------------------

    async def check_cooldown(self, user, guild):

        cooldown = await self.config.guild(guild).cooldown()

        last = await self.config.user(user).last_trigger()

        if time.time() - last < cooldown:
            return False

        await self.config.user(user).last_trigger.set(time.time())

        return True

    # ----------------------------
    # Handle violation
    # ----------------------------

    async def process_violation(self, message, swears):

        guild = message.guild
        user = message.author

        if not await self.check_cooldown(user, guild):
            return

        fine = await self.config.guild(guild).fine_amount()

        total = fine * swears

        balance = await bank.get_balance(user)

        if balance < total:
            total = balance

        if total <= 0:
            return

        await bank.withdraw_credits(user, total)

        jar = await self.config.guild(guild).jar_balance()
        jar += total

        await self.config.guild(guild).jar_balance.set(jar)

        count = await self.config.user(user).swear_count()
        count += swears

        await self.config.user(user).swear_count.set(count)

        await self.check_jackpot(message.channel, guild)

        currency = await bank.get_currency_name(guild)

        embed = discord.Embed(
            title="Swear Jar Triggered",
            color=discord.Color.red()
        )

        embed.description = f"{user.mention} triggered the swear jar."

        embed.add_field(name="Detected", value=str(swears))
        embed.add_field(name="Fine", value=f"{humanize_number(total)} {currency}")
        embed.add_field(name="Jar", value=f"{humanize_number(jar)} {currency}")

        await message.channel.send(embed=embed)

    # ----------------------------
    # Jackpot system
    # ----------------------------

    async def check_jackpot(self, channel, guild):

        threshold = await self.config.guild(guild).jackpot_threshold()

        jar = await self.config.guild(guild).jar_balance()

        if jar < threshold:
            return

        members = [m for m in guild.members if not m.bot]

        winner = members[int(time.time()) % len(members)]

        await bank.deposit_credits(winner, jar)

        await self.config.guild(guild).jar_balance.set(0)

        currency = await bank.get_currency_name(guild)

        await channel.send(
            f"💰**Swear Jar Jackpot!**💰 {winner.mention} won {jar} {currency}."
        )

    # ----------------------------
    # Message processing
    # ----------------------------

    async def process_message(self, message):

        if message.author.bot:
            return

        if not message.guild:
            return

        if not await self.config.guild(message.guild).enabled():
            return

        total_swears = 0

        if message.content:
            total_swears += self.detect_swears(message.content)

        for attachment in message.attachments:

            if attachment.content_type and "audio" in attachment.content_type:

                try:
                    transcript = await self.transcribe(attachment)
                    total_swears += self.detect_swears(transcript)
                except Exception:
                    pass

        if total_swears > 0:
            await self.process_violation(message, total_swears)

    # ----------------------------
    # Listeners
    # ----------------------------

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.process_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await self.process_message(after)

    # ----------------------------
    # Commands
    # ----------------------------

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def swearjar(self, ctx):
        pass

    @swearjar.command()
    async def fine(self, ctx, amount: int):

        await self.config.guild(ctx.guild).fine_amount.set(amount)

        currency = await bank.get_currency_name(ctx.guild)

        await ctx.send(f"Fine set to {amount} {currency}")

    @swearjar.command()
    async def cooldown(self, ctx, seconds: int):

        await self.config.guild(ctx.guild).cooldown.set(seconds)

        await ctx.send(f"Cooldown set to {seconds}s")

    @swearjar.command()
    async def jackpot(self, ctx, amount: int):

        await self.config.guild(ctx.guild).jackpot_threshold.set(amount)

        currency = await bank.get_currency_name(ctx.guild)

        await ctx.send(f"Jackpot threshold set to {amount} {currency}")
