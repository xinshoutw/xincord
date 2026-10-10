"""The plugin's cog: the boards' loops, their posts and the ready check.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:15-95
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-43
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from xincord.core.storage import Store

    from .config import Config


class NtustAnnouncements(commands.Cog):
    """The plugin's state; ``setup`` adds it."""

    def __init__(self, bot: commands.Bot, config: Config, store: Store) -> None:
        """Keep the bot, the config and the store of the boards' posted lists.

        A reload builds a new cog from the new config: v3's reload kept the keys, the prompt and
        the interval that it had read first.
        """
        self.bot = bot
        self.config = config
        self.store = store
