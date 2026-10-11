"""Economy: each guild's wallets of money and spending, which listed administrators change."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import COMMANDS, IDS, Economy, check_boards
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Discord resolves the member option in the interaction, and nothing reads the member cache.
INTENTS = discord.Intents.none()
# Replies use the user's locale and fall back to this one.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files, the templates and the config, then register the cog's handlers.

    The lang files load first, so that they are written even while the config waits for an
    administrator. The wallets are in the shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    templates = Templates.load(lang)
    check_boards(lang, templates)
    cog = Economy(context.config(Config), context.store, lang, templates)
    await bot.add_cog(cog)
    # Guild commands; discord.py removes them when the plugin unloads.
    for name in COMMANDS:
        bot.tree.add_command(cog.command(name))
    # Buttons with IDS's IDs, legacy economy@ ones too, reach cog.handle; the core drops the route
    # when the plugin unloads.
    bot.route(__name__, IDS, cog.handle)
