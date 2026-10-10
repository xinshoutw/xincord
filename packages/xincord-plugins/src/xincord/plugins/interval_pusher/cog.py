"""The loops that push each listener's URL.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/Event.kt:10-54
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from .config import Config


class IntervalPusher(commands.Cog):
    """The plugin's state and loops; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config) -> None:
        """Keep the bot and the configured listeners, in the config's order."""
        self.bot = bot
        self.listeners = config.listeners
