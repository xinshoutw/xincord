"""Ticket: administrators build ticket panels; members open private ticket channels from them."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import Ticket
from .ids import IDS

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Guild leaves need only discord.py's default guilds intent; the members come with the
# interactions, and the archive reads the channels' history through REST.
INTENTS = discord.Intents.none()
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates and add the cog; panels are in the shared store.

    No config: the core's ``plugins`` list enables the plugin.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = Ticket(bot, context.store, lang, Templates.load(lang))
    await bot.add_cog(cog)
    # Guild commands; discord.py removes them when the plugin unloads.
    for command in cog.commands():
        bot.tree.add_command(command)
    # The builder's, the panels' and the tickets' components and modals, legacy IDs too, go to
    # cog.handle; the core drops the route when the plugin unloads.
    bot.route(__name__, IDS, cog.handle)
