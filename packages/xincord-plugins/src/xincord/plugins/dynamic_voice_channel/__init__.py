"""DynamicVoiceChannel: members who join a bound lobby alone get a voice room of their own.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/Event.kt:21-78
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import DynamicVoiceChannel

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()  # v3's SQLiteAPI was never used
SOFT_DEPENDS: tuple[str, ...] = ()
# v3's GUILD_VOICE_STATES: voice updates and the members of each voice channel.
INTENTS = discord.Intents(voice_states=True)
# Replies use the user's locale and fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog.

    The plugin has no config: v3's only key was ``enabled``. Its bindings and rooms are in the
    shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    await bot.add_cog(DynamicVoiceChannel(bot, context.store, lang, Templates.load(lang)))
