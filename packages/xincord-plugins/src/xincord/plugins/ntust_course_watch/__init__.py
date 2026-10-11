"""NtustCourseWatch: members register NTUST courses and hear when they have seats."""

from typing import TYPE_CHECKING

import discord

from .cog import COMMANDS, NtustCourseWatch
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
    """Load the config and the lang files, then add the cog and its commands."""
    context = bot.plugin_context(__name__)
    config = context.config(Config)
    lang = context.lang(DEFAULT_LOCALE)
    cog = NtustCourseWatch(bot, config, context.store, lang)
    await bot.add_cog(cog)
    # Guild commands, as in v3. discord.py removes them when the plugin unloads.
    for name in COMMANDS:
        bot.tree.add_command(cog.command(name))
