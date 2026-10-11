"""Giveaway: administrators build and post a giveaway; members join and winners are drawn."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import IDS, Giveaway
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Guild leaves need only discord.py's default guilds intent, and the members come with the
# interactions, as in v3.
INTENTS = discord.Intents.none()


async def setup(bot: Bot) -> None:
    """Load the config, then the lang files with its default locale and the templates; add the cog.

    The giveaways are in the shared store.
    """
    context = bot.plugin_context(__name__)
    config = context.config(Config)
    lang = context.lang(config.default_locale)
    cog = Giveaway(bot, config, context.store, lang, Templates.load(lang))
    await bot.add_cog(cog)
    # A guild command, as in v3. discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
    # The builder's buttons and modals and the posts' buttons with IDS's IDs, v3's too, reach
    # cog.handle; the core drops the route when the plugin unloads.
    bot.route(__name__, IDS, cog.handle)
