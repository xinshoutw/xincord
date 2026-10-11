"""The command, the menu's components, the message listeners and the checks at READY."""

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

from .created import parse_created
from .logs import Place, author_values, message_url, unknown_author
from .messages import MessageFiles, Stored
from .text import fit, message_text

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.plugins import PluginContext
    from xincord.core.templates import Templates

    from .config import Config

logger = logging.getLogger(__name__)

NAMESPACE = "ChatLogger"  # the plugin's name: its settings in the store
# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("chat_logger", ("action",), legacy_prefix="chat-logger@")
ROOT = "chat-logger"  # v3's command, and the root of its register.yaml keys
MENU = "chat-logger@setting"  # the settings menu's template
HOUR = 3600  # seconds between the deletions of the messages older than the retention
MIB = 1024 * 1024  # the unit of max_file_size_mb

type Sleep = Callable[[float], Awaitable[object]]


class ChatLogger(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(
        self,
        bot: commands.Bot,
        context: PluginContext,
        config: Config,
        lang: Lang,
        templates: Templates,
    ) -> None:
        """Keep the bot, the config, the store and what ``setup`` loaded.

        The stored messages are in files of the plugin's data directory, which :meth:`cog_load`
        opens and :meth:`cog_unload` closes.
        """
        self.bot = bot
        self.config = config
        self.store = context.store
        self.lang = lang
        self.settings = ListenSettings(context.store, NAMESPACE)
        self.messages = MessageFiles(context.data_directory, config.max_file_size_mb * MIB)
        # The menu, its components, the posts and the checks at READY, shared with VoiceLogger.
        self.listen = ListenChannels(bot, self.settings, Menu(lang, templates, IDS, "cl", MENU))
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # the retention loop once loaded
        # The messages whose insert is under way, by ID; their edits and deletions wait for it.
        self.inserting: dict[int, asyncio.Event] = {}
        self.sleep: Sleep = asyncio.sleep  # between the retention's deletions

    @override
    async def cog_load(self) -> None:
        """Open the message files, check a ready bot's guilds, then start the retention loop.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is deleted before READY; in a ready bot, as after a reload, the guilds are checked at
        once, since no ``on_ready`` follows, and the loop deletes at once. The checks come before
        the loop: when they fail, the plugin does not load, its files close again, and no loop is
        left behind.
        """
        await self.messages.open()
        try:
            if self.bot.is_ready():
                await self.check_guilds()
        except BaseException:
            await self.messages.close()
            raise
        self.tasks = (asyncio.create_task(self._retain(), name="ChatLogger retention"),)

    @override
    async def cog_unload(self) -> None:
        """Cancel the retention loop and wait for it, then close the message files.

        discord.py runs this when the plugin unloads, before a reload's new version loads, and
        when the bot closes. The files close after the store work under way; a listener of this
        version that stores afterwards fails, as the plugin is gone.
        """
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.messages.close()

    async def _retain(self) -> None:
        """Delete the old messages when the bot is ready, then every hour.

        v3 kept every message forever; the retention keeps the files from growing without limit.
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
    async def on_gateway_message_create(self, payload: dict[str, object]) -> None:
        """Store a guild message that the bot did not send, other bots' and webhooks' included.

        ``setup`` relays ``MESSAGE_CREATE``: discord.py hands ``on_message`` its cached message,
        which an edit parsed before the listener runs changes in place, while the payload keeps
        the text that the message was sent with. With ``log_all`` false, only when a listen
        channel of the guild detects its channel; v3 stored only the channels that had a table
        already. The message's edits and deletions wait for this insert (``inserting``).
        """
        created = parse_created(payload)
        if created is None or self._own(created.author_id):
            return
        guild = self.bot.get_guild(created.guild_id)
        channel = None if guild is None else guild.get_channel_or_thread(created.channel_id)
        place = Place.of(created.channel_id, channel)
        inserted = self.inserting.setdefault(created.message_id, asyncio.Event())
        try:
            if self.config.log_all or await self._targets(created.guild_id, place):
                await self.messages.add(
                    created.message_id, created.guild_id, place.id, created.author_id, created.text
                )
        finally:
            inserted.set()
            self.inserting.pop(created.message_id, None)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        """Log a stored message's new text to the listen channels that detect its channel.

        Every ``MESSAGE_UPDATE`` arrives, the message cached or not, as JDA's event did, with the
        updated message that discord.py builds from it. Only a stored message whose text changed
        counts: v3 counted every update, a pin or a link preview too. The author is the message's,
        the member from the update (v3's ``Placeholder.get(event.member)``).
        """
        message, guild_id = payload.message, payload.guild_id
        if guild_id is None or self._own(message.author.id):
            return
        place = Place.of(payload.channel_id, message.channel)
        # Only bots and webhooks send embeds: a member's are link previews (rich ones too).
        sender = message.author.bot or message.webhook_id is not None
        text = message_text(message.content, message.embeds if sender else ())
        await self._inserted([payload.message_id])
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

        The message leaves the store either way unless ``keep_deleted`` keeps it, as v3 kept the
        text of deleted messages.
        """
        if payload.guild_id is None:
            return
        place = self._place(payload.guild_id, payload.channel_id)
        await self._inserted([payload.message_id])
        stored = await self.messages.pop(payload.message_id, keep=self.config.keep_deleted)
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
        await self._inserted(payload.message_ids)
        taken = await self.messages.pop_all(payload.message_ids, keep=self.config.keep_deleted)
        await self._log_deletions(payload.guild_id, place, [stored for _, stored in taken])

    def _place(self, guild_id: int, channel_id: int) -> Place:
        """The place of a channel of the guild, from discord.py's cache, read before any await."""
        guild = self.bot.get_guild(guild_id)
        channel = None if guild is None else guild.get_channel_or_thread(channel_id)
        return Place.of(channel_id, channel)

    async def _log_deletions(self, guild_id: int, place: Place, deleted: list[Stored]) -> None:
        """Post v3's deletion embed of each message of ``deleted`` to the detecting channels.

        The members are fetched only when a listen channel detects the channel, once per author.
        A listen channel that is gone or forbids the bot is not tried again for the other
        messages of a bulk deletion.
        """
        guild = self.bot.get_guild(guild_id)
        if not deleted or guild is None:
            return
        listen = await self._targets(guild.id, place)
        authors: dict[int, dict[str, str]] = {}
        for stored in deleted:
            if not listen:
                return
            if stored.user_id not in authors:
                authors[stored.user_id] = await self._author(guild, stored.user_id)
            values = place.values() | {
                "cl_change_count": str(stored.count),
                "cl_msg_before": fit(stored.text),
            }
            author = authors[stored.user_id]
            failed = await self.listen.post(guild, listen, "on-msg-delete", author | values)
            listen = [channel for channel in listen if channel not in failed]

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

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Check the guilds when the bot is ready, for each session."""
        await self.check_guilds()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Delete the data of a guild that the bot left or was removed from.

        The settings go at once (v3 deleted them at its next start), and the stored messages with
        ``log_all`` false, as v3 meant to: its deletion used a key without the ``CL:`` prefix and
        deleted nothing. With ``log_all`` true, v3 kept them; the retention deletes them now.
        discord.py does not fire this during an outage.
        """
        await self.settings.forget(guild.id)
        if not self.config.log_all:
            await self.messages.forget(guild.id)

    async def check_guilds(self) -> None:
        """Forget the guilds that the bot left while offline, and drop deleted list entries.

        The settings are checked as VoiceLogger's; the stored messages follow ``log_all``.
        """
        await self.listen.check_guilds()
        await self.forget_left_guilds()

    async def forget_left_guilds(self) -> None:
        """Delete the stored messages of the guilds that the bot left, with ``log_all`` false.

        By ``on_ready``, discord.py knows every guild of the session, unavailable ones included.
        v3 deleted such guilds' database files at its start with ``log_all`` false, and kept them
        with true.
        """
        if self.config.log_all:
            return
        for guild_id in await self.messages.guild_ids():
            if self.bot.get_guild(guild_id) is None:
                await self.messages.forget(guild_id)
                logger.info(
                    "ChatLogger deleted the stored messages of guild %s, which the bot left",
                    guild_id,
                )

    async def _inserted(self, message_ids: Iterable[int]) -> None:
        """Wait for the inserts of these messages that are under way.

        discord.py runs listeners as concurrent tasks: an edit or a deletion that arrives right
        after its message reaches the store after the message's insert, which waits for the
        settings first with ``log_all`` false.
        """
        for message_id in message_ids:
            if (inserting := self.inserting.get(message_id)) is not None:
                await inserting.wait()

    def _own(self, user_id: int) -> bool:
        """Whether ``user_id`` is the bot's, whose messages v3 did not store."""
        bot = self.bot.user
        return bot is not None and user_id == bot.id

    async def _targets(self, guild_id: int, place: Place) -> list[int]:
        """The listen channels of the guild that detect ``place``, in stored order."""
        return targets(await self.settings.read_settings(guild_id), [place.ids])
