"""AutoRole: members who join a configured guild get that guild's roles.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/Event.kt:7-31
"""

from typing import TYPE_CHECKING

import discord

from .cog import AutoRole
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Member joins need the privileged members intent, which v3's core always requested.
INTENTS = discord.Intents(members=True)


async def setup(bot: Bot) -> None:
    """Load the config and add the cog.

    The plugin has no lang files: v3 had no text.
    """
    context = bot.plugin_context(__name__)
    await bot.add_cog(AutoRole(bot, context.config(Config)))
