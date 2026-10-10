"""NtustAnnouncements (v3 NtustManager): new announcements on NTUST's boards, posted to Discord.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-43
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/resources/info.yaml:1-8
"""

from typing import TYPE_CHECKING

import discord

from .cog import NtustAnnouncements
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# No gateway events beyond READY: v3's plugin was no listener. The guilds intent of discord.py's
# defaults caches the channels that the ready check looks up.
INTENTS = discord.Intents.none()


async def setup(bot: Bot) -> None:
    """Load the config and add the cog.

    The plugin has no lang files: v3 had none, and its only text is built in code.
    """
    context = bot.plugin_context(__name__)
    await bot.add_cog(NtustAnnouncements(bot, context.config(Config), context.store))
