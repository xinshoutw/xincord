"""VoiceLogger: voice joins, leaves, switches and status changes, posted to listen channels.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/Event.kt:23-110
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import VoiceLogger

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# v3's GUILD_VOICE_STATES: voice updates and the voice channels' members. discord.py's default
# guilds intent carries the voice channel status updates.
INTENTS = discord.Intents(voice_states=True)
# The menu uses the user's locale and the logs the guild's; both fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog.

    The plugin has no config: v3's only key was ``enabled``. Its settings are in the shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    await bot.add_cog(VoiceLogger(bot, context.store, lang, Templates.load(lang)))
