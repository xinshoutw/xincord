"""Example, the template plugin: copy this package to start a new plugin.

``/example-command`` answers with its two options and the config's ``example_key`` in an
ephemeral embed, under a button that counts its presses.
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import IDS, Example
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

# Read by the core before the plugin loads: the plugins this one needs, those it uses when they are
# enabled, and the gateway intents it adds to discord.py's defaults.
DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
INTENTS = discord.Intents.none()
# Replies use the user's locale and fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the config, the lang files and the templates, then register the cog's handlers."""
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = Example(context.config(Config), lang, Templates.load(lang))
    await bot.add_cog(cog)
    # A guild command: no extras={"global": True}. discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
    # Buttons with IDS's IDs reach cog.count; the core drops the route when the plugin unloads.
    bot.route(__name__, IDS, cog.count)
