"""BasicCalculator: ``/basic-calculate`` evaluates a formula exactly and posts the result.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/Event.kt:14-62
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import BasicCalculator

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
INTENTS = discord.Intents.none()
# Replies use the user's locale and fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog.

    The plugin has no config: v3's only key was ``enabled``.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    await bot.add_cog(BasicCalculator(lang, Templates.load(lang)))
