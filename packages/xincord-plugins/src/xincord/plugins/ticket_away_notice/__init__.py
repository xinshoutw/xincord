"""TicketAwayNotice (v3 TicketAddons): new ticket channels get a notice while the owner is offline.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:7-30
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/resources/info.yaml:1-13
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import TicketAwayNotice
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# The owner's status needs the privileged presences intent, and the privileged members intent keeps
# the guild's members in discord.py's cache for the presences to land on; v3 asked for presences
# but cached no members, so it read the owner as offline almost always.
INTENTS = discord.Intents(members=True, presences=True)
DEFAULT_LOCALE = "zh-TW"  # v3's only locale, in which the notice is posted for everyone


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then the config, and add the cog.

    The lang files load first, so that they are written even while the bundled config waits for
    the IDs. The plugin keeps no data.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    templates = Templates.load(lang)
    await bot.add_cog(TicketAwayNotice(bot, context.config(Config), lang, templates))
