"""NtustCourseWatch (v3 NtustCourse): members register NTUST courses and hear when they have seats.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:14-61
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/resources/info.yaml:1-8
"""

from typing import TYPE_CHECKING

import discord

from .cog import NtustCourseWatch
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Slash commands need no intent, and the alerts go through partial messageables, which need no
# cache: v3's info.yaml requested nothing either.
INTENTS = discord.Intents.none()
# v3's texts were all English: the en-US files hold them, and zh-TW translates them.
DEFAULT_LOCALE = "en-US"


async def setup(bot: Bot) -> None:
    """Load the config and the lang files, then add the cog."""
    context = bot.plugin_context(__name__)
    config = context.config(Config)
    lang = context.lang(DEFAULT_LOCALE)
    await bot.add_cog(NtustCourseWatch(bot, config, context.store, lang))
