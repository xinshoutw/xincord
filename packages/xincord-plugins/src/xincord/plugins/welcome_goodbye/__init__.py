"""WelcomeGoodbye: members who join or leave a guild are welcomed or seen off in bound channels."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import COMMANDS, WelcomeGoodbye

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Member joins and removals need the privileged members intent.
INTENTS = discord.Intents(members=True)
# Replies and messages use the guild's locale and fall back to this one.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog and its commands.

    The plugin has no config. Its data is in the shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = WelcomeGoodbye(bot, context.store, lang, Templates.load(lang))
    await bot.add_cog(cog)
    # Guild commands; discord.py removes them when the plugin unloads.
    for name in COMMANDS:
        bot.tree.add_command(cog.command(name))
