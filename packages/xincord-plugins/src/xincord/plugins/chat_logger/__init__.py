"""ChatLogger: stored guild messages, whose edits and deletions are posted to listen channels."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import IDS, ChatLogger
from .config import Config
from .created import EVENT
from .messages import DROP_OLD_TABLE

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Guild messages and their content. The message content intent is privileged: Discord refuses
# the connection unless the developer portal allows it, and messages carry no text without it.
INTENTS = discord.Intents(guild_messages=True, message_content=True)
# The menu uses the user's locale and the logs the guild's; both fall back to this one.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files, the templates and the config, then add the cog.

    The settings are in the shared store, the stored messages in the plugin's own files under
    ``data/ChatLogger/``, which the cog opens when it is added and closes when it is removed.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    templates = Templates.load(lang)
    cog = ChatLogger(bot, context, context.config(Config), lang, templates)
    # Earlier builds' table of messages in the shared store goes, without its rows.
    await context.store.run(lambda db: db.execute(DROP_OLD_TABLE))
    await bot.add_cog(cog)
    # A guild command; discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
    # The menu's buttons and select menus with IDS's IDs, legacy ones too, reach cog.handle; the
    # core drops the route when the plugin unloads.
    bot.route(__name__, IDS, cog.handle)
    # New messages reach cog.on_gateway_message_create as Discord sent them: discord.py's cached
    # message, which on_message gets, takes later edits in place.
    bot.relay_gateway_event(EVENT)
