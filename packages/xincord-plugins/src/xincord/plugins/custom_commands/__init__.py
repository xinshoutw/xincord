"""CustomCommands: five admin commands post a shop's bank payment instructions in the channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:14-62
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import COMMANDS, CustomCommands

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
INTENTS = discord.Intents.none()
# v3's only locale. The messages are public, so every user gets them in it, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog and its commands.

    The plugin has no config: v3's only key was ``enabled``.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = CustomCommands(lang, Templates.load(lang))
    await bot.add_cog(cog)
    # Guild commands, as in v3. discord.py removes them when the plugin unloads.
    for name in COMMANDS:
        bot.tree.add_command(cog.command(name))
