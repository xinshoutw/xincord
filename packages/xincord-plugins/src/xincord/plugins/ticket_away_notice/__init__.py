"""TicketAwayNotice: new ticket channels get a notice while the owner is offline."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import TicketAwayNotice, check_notice
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# The owner's status needs the privileged presences intent, and the privileged members intent keeps
# the guild's members in discord.py's cache for the presences to land on.
INTENTS = discord.Intents(members=True, presences=True)
DEFAULT_LOCALE = "zh-TW"  # the only locale, in which the notice is posted for everyone


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, check the notice, then the config, and add the cog.

    The lang files load first, so that they are written even while the bundled config waits for
    the IDs. The plugin keeps no data.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    templates = Templates.load(lang)
    check_notice(lang, templates)
    await bot.add_cog(TicketAwayNotice(bot, context.config(Config), lang, templates))
