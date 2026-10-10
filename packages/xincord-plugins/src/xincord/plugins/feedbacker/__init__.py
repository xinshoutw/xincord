"""Feedbacker: administrators ask a member to rate the service; the review goes to a channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Event.kt:15-75
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import Feedbacker
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Discord resolves the member option and the submitter, and the submit channel comes from the guild
# cache that discord.py's default intents fill.
INTENTS = discord.Intents.none()
# The prompt and the modal use the user's locale and the review the guild's; each falls back to
# this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the config, the lang files and the templates, then add the cog."""
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    await bot.add_cog(Feedbacker(context.config(Config), lang, Templates.load(lang)))
