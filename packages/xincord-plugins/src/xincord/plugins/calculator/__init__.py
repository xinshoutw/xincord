"""Calculator: ``/basic-calculate`` evaluates a formula exactly and posts the result."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import Calculator

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
INTENTS = discord.Intents.none()
# Replies use the user's locale and fall back to this one.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog and its command.

    The plugin has no config.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = Calculator(lang, Templates.load(lang))
    await bot.add_cog(cog)
    # A guild command; discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
