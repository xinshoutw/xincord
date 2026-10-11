"""MusicPlayer: a per-guild music player whose audio a Lavalink node plays.

Members bring the bot into voice with ``/join`` or ``/play`` and control the songs with v3's
commands and the buttons of an ephemeral panel that refreshes itself.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:16-62
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/resources/info.yaml:1-19
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import MusicPlayer
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

# v3 depended on AudioAPI only to load after it; its libraries fold into this plugin (B12).
DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# v3's GUILD_VOICE_STATES (in discord.py's defaults, declared anyway): members' voice channels come
# from the guilds' voice states, which need no member cache.
INTENTS = discord.Intents(voice_states=True)
# v3's templates fell back to zh-TW; its commands' English base texts stay in the code.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files, the config and the templates, then add the cog."""
    context = bot.plugin_context(__name__)
    # The lang files first, so that they are written while the config waits for the password.
    lang = context.lang(DEFAULT_LOCALE)
    config = context.config(Config)
    cog = MusicPlayer(bot, config, lang, Templates.load(lang))
    await bot.add_cog(cog)
