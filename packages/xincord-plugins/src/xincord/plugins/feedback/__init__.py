"""Feedback: administrators ask a member to rate the service; the review goes to a channel."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import IDS, Feedback
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Discord resolves the member option and the submitter, and the submit channel comes from the guild
# cache that discord.py's default intents fill.
INTENTS = discord.Intents.none()
# The prompt and the modal use the user's locale and the review the guild's; each falls back to
# this one.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the config, the lang files and the templates, then register the cog's handlers."""
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = Feedback(context.config(Config), lang, Templates.load(lang))
    await bot.add_cog(cog)
    # A guild command; discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
    # Star presses and submitted modals with IDS's IDs, legacy ones too, reach cog.handle; the core
    # drops the route when the plugin unloads.
    bot.route(__name__, IDS, cog.handle)
