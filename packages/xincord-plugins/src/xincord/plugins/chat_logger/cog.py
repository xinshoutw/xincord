"""The command, the menu's components, the message listeners and the checks at READY.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:31-382
"""

import asyncio
import logging
import sqlite3
from datetime import timedelta
from typing import TYPE_CHECKING, Any, override

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import time_snowflake, utcnow

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import global_values
from xincord.plugins.listen_channels.menu import ListenChannels, Menu
from xincord.plugins.listen_channels.settings import targets
from xincord.plugins.listen_channels.store import ListenSettings

from .logs import Place, author_values, message_url, unknown_author
from .messages import MessageLog, Stored
from .text import fit, message_text

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .config import Config

logger = logging.getLogger(__name__)

NAMESPACE = "ChatLogger"  # the plugin's name: its settings in the store
# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("chat_logger", ("action",), legacy_prefix="chat-logger@")
ROOT = "chat-logger"  # v3's command, and the root of its register.yaml keys
MENU = "chat-logger@setting"  # the settings menu's template
HOUR = 3600  # seconds between the deletions of the messages older than the retention

type Sleep = Callable[[float], Awaitable[object]]


class ChatLogger(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(
        self, bot: commands.Bot, config: Config, store: Store, lang: Lang, templates: Templates
    ) -> None:
        """Keep the bot, the config, the store and what ``setup`` loaded."""
        self.bot = bot
        self.config = config
        self.store = store
        self.lang = lang
        self.settings = ListenSettings(store, NAMESPACE)
        self.messages = MessageLog(store)
        # The menu, its components, the posts and the checks at READY, shared with VoiceLogger.
        self.listen = ListenChannels(bot, self.settings, Menu(lang, templates, IDS, "cl", MENU))
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # the retention loop once loaded
        self.sleep: Sleep = asyncio.sleep  # between the retention's deletions

    @override
    async def cog_load(self) -> None:
        """Start the retention loop, which waits until the bot is ready.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is deleted before READY; in a ready bot, as after a reload, the loop deletes at once.
        """
        self.tasks = (asyncio.create_task(self._retain(), name="ChatLogger retention"),)

    @override
    async def cog_unload(self) -> None:
        """Cancel the retention loop and wait for it, before the store closes."""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def _retain(self) -> None:
        """Delete the old messages when the bot is ready, then every hour.

        v3 kept every message forever; the retention keeps the store from growing without limit.
        """
        await self.bot.wait_until_ready()
        while True:
            await self.prune()
            await self.sleep(HOUR)

    async def prune(self) -> None:
        """Delete the stored messages created more than ``retention_days`` days ago.

        A message's ID tells when it was created. A failure is logged, and the next hour tries
        again.
        """
        days = self.config.retention_days
        before = time_snowflake(utcnow() - timedelta(days=days))
        try:
            deleted = await self.messages.prune(before)
        except sqlite3.Error:
            logger.exception("ChatLogger cannot delete the messages older than %s days", days)
            return
        logger.debug("ChatLogger deleted %s messages older than %s days", deleted, days)

    def command(self) -> app_commands.Group:
        """Build v3's ``/chat-logger`` with its subcommand ``setting``, from ``register.yaml``.

        As in v3, only administrators see it by default; there is no other check. The group is
        built here, so its module is the plugin's and unloading the plugin removes it.
        """
        lang = self.lang
        group = app_commands.Group(
            name=lang.command(ROOT, f"{ROOT}.name"),
            description=lang.command("commands about chat logger", f"{ROOT}.description"),
            default_permissions=discord.Permissions(administrator=True),
        )
        key = f"{ROOT}.subcommands.setting"
        setting: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("setting", f"{key}.name"),
            description=lang.command("set chat log in this channel", f"{key}.description"),
            callback=self.show_settings,
        )
        group.add_command(setting)
        return group

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the channel's settings menu (v3's ``setting``)."""
        await self.listen.show(interaction)

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Change the settings from the menu's buttons and select menus; ``setup`` routes here."""
        await self.listen.handle(interaction, parsed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Store a guild message that the bot did not send, other bots' and webhooks' included.

        With ``log_all`` false, only when a listen channel of the guild detects its channel; v3
        stored only the channels that had a table already, a set that no setting changed.
        """
        guild = message.guild
        if guild is None or self._own(message.author):
            return
        place = Place.of(message.channel.id, message.channel)
        text = message_text(message.content, message.embeds)
        if not self.config.log_all and not await self._targets(guild.id, place):
            return
        await self.messages.add(message.id, guild.id, place.id, message.author.id, text)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        """Log a stored message's new text to the listen channels that detect its channel.

        Every ``MESSAGE_UPDATE`` arrives, the message cached or not, as JDA's event did, with the
        updated message that discord.py builds from it. Only a stored message whose text changed
        counts: v3 counted every update, a pin or a link preview too. The author is the message's,
        the member from the update (v3's ``Placeholder.get(event.member)``).
        """
        message, guild_id = payload.message, payload.guild_id
        if guild_id is None or self._own(message.author):
            return
        place = Place.of(payload.channel_id, message.channel)
        text = message_text(message.content, message.embeds)
        edit = await self.messages.edit(payload.message_id, text)
        guild = self.bot.get_guild(guild_id)
        if edit is None or guild is None:
            return
        listen = await self._targets(guild.id, place)
        if not listen:
            return
        bot = self.bot.user
        author = {} if bot is None else author_values(message.author, bot)
        values = place.values() | {
            "cl_msg_after_url": message_url(guild.id, place.id, payload.message_id),
            "cl_change_count": str(edit.count),
            "cl_msg_before": fit(edit.before),
            "cl_msg_after": fit(text),
        }
        await self.listen.post(guild, listen, "on-msg-update", author | values)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Log a deleted stored message to the listen channels that detect its channel.

        The message leaves the store either way: v3 kept the text of deleted messages, which
        nothing needs once the deletion is handled.
        """
        if payload.guild_id is None:
            return
        place = self._place(payload.guild_id, payload.channel_id)
        stored = await self.messages.pop(payload.message_id)
        await self._log_deletions(payload.guild_id, place, [] if stored is None else [stored])

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
        """Log each stored message of a bulk deletion, oldest first, as a deletion of its own.

        v3 never logged them: its core turned JDA's splitting of bulk deletions off, and the
        plugin ignored ``MessageBulkDeleteEvent``.
        """
        if payload.guild_id is None:
            return
        place = self._place(payload.guild_id, payload.channel_id)
        taken = await self.messages.pop_all(payload.message_ids)
        await self._log_deletions(payload.guild_id, place, [stored for _, stored in taken])

    def _place(self, guild_id: int, channel_id: int) -> Place:
        """The place of a channel of the guild, from discord.py's cache, read before any await."""
        guild = self.bot.get_guild(guild_id)
        channel = None if guild is None else guild.get_channel_or_thread(channel_id)
        return Place.of(channel_id, channel)

    async def _log_deletions(self, guild_id: int, place: Place, deleted: list[Stored]) -> None:
        """Post v3's deletion embed of each message of ``deleted`` to the detecting channels.

        The members are fetched only when a listen channel detects the channel, once per author.
        """
        guild = self.bot.get_guild(guild_id)
        if not deleted or guild is None:
            return
        listen = await self._targets(guild.id, place)
        if not listen:
            return
        authors: dict[int, dict[str, str]] = {}
        for stored in deleted:
            if stored.user_id not in authors:
                authors[stored.user_id] = await self._author(guild, stored.user_id)
            values = place.values() | {
                "cl_change_count": str(stored.count),
                "cl_msg_before": fit(stored.text),
            }
            await self.listen.post(guild, listen, "on-msg-delete", authors[stored.user_id] | values)

    async def _author(self, guild: discord.Guild, user_id: int) -> dict[str, str]:
        """The keys of a stored author, fetched as the guild's member (v3's ``retrieveMemberById``).

        A user who left, a webhook or a refusal gives the stored ID's mention and ``-``: v3 posted
        nothing then.
        """
        bot = self.bot.user
        try:
            member = await guild.fetch_member(user_id)
        except discord.HTTPException:
            return global_values(self.bot) | unknown_author(user_id)
        return {} if bot is None else author_values(member, bot)

    def _own(self, author: discord.abc.Snowflake) -> bool:
        """Whether ``author`` is the bot, whose messages v3 did not store."""
        bot = self.bot.user
        return bot is not None and author.id == bot.id

    async def _targets(self, guild_id: int, place: Place) -> list[int]:
        """The listen channels of the guild that detect ``place``, in stored order."""
        return targets(await self.settings.read_settings(guild_id), [place.ids])
