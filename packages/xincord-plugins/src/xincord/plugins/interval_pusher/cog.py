"""The loops that push each listener's URL.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/Event.kt:10-54
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from .config import Config, Listener


class IntervalPusher(commands.Cog):
    """The plugin's state and loops; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config) -> None:
        """Keep the bot and what ``setup`` loaded."""
        self.bot = bot
        self.config = config

    @property
    def listeners(self) -> tuple[Listener, ...]:
        """The configured listeners, in the config's order."""
        raise NotImplementedError
