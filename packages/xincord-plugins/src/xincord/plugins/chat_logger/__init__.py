"""ChatLogger: stored guild messages, whose edits and deletions are posted to listen channels.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:23-131
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import ChatLogger
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()  # v3's SQLiteAPI is the core's store
SOFT_DEPENDS: tuple[str, ...] = ()
# v3's GUILD_MESSAGES and MESSAGE_CONTENT. The message content intent is privileged: Discord refuses
# the connection unless the developer portal allows it, and messages carry no text without it.
INTENTS = discord.Intents(guild_messages=True, message_content=True)
# The menu uses the user's locale and the logs the guild's; both fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files, the templates and the config, then add the cog.

    The settings and the messages are in the shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    templates = Templates.load(lang)
    cog = ChatLogger(bot, context.config(Config), context.store, lang, templates)
    await bot.add_cog(cog)
