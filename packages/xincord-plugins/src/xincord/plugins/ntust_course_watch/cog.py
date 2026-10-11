"""The plugin's cog.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:14-61
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:15-142
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store

    from .config import Config


class NtustCourseWatch(commands.Cog):
    """The plugin's state; ``setup`` adds it."""

    def __init__(self, bot: commands.Bot, config: Config, store: Store, lang: Lang) -> None:
        """Keep the bot, the config, the store of the registrations and the texts.

        A reload builds a new cog from the new config.
        """
        self.bot = bot
        self.config = config
        self.store = store
        self.lang = lang
