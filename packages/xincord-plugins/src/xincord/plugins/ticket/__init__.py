"""Ticket: administrators build ticket panels; members open private ticket channels from them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Event.kt:18-89
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import Ticket

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Guild leaves need only discord.py's default guilds intent; the members come with the
# interactions, and the archive reads the channels' history through REST, as v3.
INTENTS = discord.Intents.none()
DEFAULT_LOCALE = "zh-TW"  # v3's default locale


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates and add the cog; panels are in the shared store.

    No config: v3's only key was ``enabled``, which the core's ``plugins`` list replaces.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = Ticket(bot, context.store, lang, Templates.load(lang))
    await bot.add_cog(cog)
    # Guild commands, as in v3. discord.py removes them when the plugin unloads.
    for command in cog.commands():
        bot.tree.add_command(command)
