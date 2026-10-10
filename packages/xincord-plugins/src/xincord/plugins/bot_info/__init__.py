"""BotInfo: ``/bot-info`` shows the bot's guild and member counts and a link to its source code.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/Event.kt:13-60
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import BotInfo
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# discord.py keeps each guild's member count current from member join and leave events, which need
# the privileged members intent; v3's core always requested it.
INTENTS = discord.Intents(members=True)
# Replies use the user's locale and fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the config, the lang files and the templates, then add the cog and its command."""
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = BotInfo(context.config(Config), lang, Templates.load(lang))
    await bot.add_cog(cog)
    # A global command, as in v3. discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
