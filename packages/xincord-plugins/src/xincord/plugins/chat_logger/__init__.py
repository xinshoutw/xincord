"""ChatLogger: stored guild messages, whose edits and deletions are posted to listen channels.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:23-131
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import IDS, ChatLogger
from .config import Config
from .created import EVENT

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
    # The stored messages' table in the shared store, before any listener runs.
    await cog.messages.create()
    await bot.add_cog(cog)
    # A guild command, as in v3. discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
    # The menu's buttons and select menus with IDS's IDs, v3's too, reach cog.handle; the core
    # drops the route when the plugin unloads.
    bot.route(__name__, IDS, cog.handle)
    # New messages reach cog.on_gateway_message_create as Discord sent them: discord.py's cached
    # message, which on_message gets, takes later edits in place.
    bot.relay_gateway_event(EVENT)
