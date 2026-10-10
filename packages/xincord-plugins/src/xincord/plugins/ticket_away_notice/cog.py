"""The listeners that post the away notice in new ticket channels while the owner is offline.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:11-39
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:26-29
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol, override, runtime_checkable

import discord
from discord.ext import commands

from xincord.core.config import ConfigError
from xincord.core.placeholders import global_values
from xincord.core.templates import TemplateError, render_message

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config

type Sleep = Callable[[float], Awaitable[object]]

NOTICE = "not-online"  # v3's template
logger = logging.getLogger(__name__)


@runtime_checkable
class Postable(Protocol):
    """A new channel that takes messages, as the plugin calls it.

    Text, announcement, voice and stage channels and threads have ``send``; categories and forum
    channels do not.
    """

    @property
    def id(self) -> int:
        """The channel's ID."""
        ...

    @property
    def name(self) -> str:
        """The channel's name."""
        ...

    async def send(
        self,
        *,
        content: str | None = None,
        embeds: Sequence[discord.Embed] = (),
        view: discord.ui.View | discord.ui.LayoutView | None = None,
        files: Sequence[discord.File] = (),
    ) -> object:
        """Send a message to the channel."""
        ...


class TicketAwayNotice(commands.Cog):
    """The plugin's state and listeners; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the config and the notice's template.

        A reload builds a new cog from the files, as v3's ``reload()`` rebuilt its template.
        """
        self.bot = bot
        self.config = config
        self.lang = lang
        self.templates = templates
        self.sleep: Sleep = asyncio.sleep  # the wait before a notice, which tests replace
        self.notices: set[asyncio.Task[None]] = set()  # the notices under way
        self.closed = False  # set when the cog unloads; no notice starts after it

    @override
    async def cog_load(self) -> None:
        """Check the guild and the owner at once when the plugin loads into a ready bot."""
        if self.bot.is_ready():
            self.check()

    @override
    async def cog_unload(self) -> None:
        """Cancel the notices under way and wait for them to end.

        An unload and a reload remove the cog, so a notice that waits then is dropped; v3's
        ``queueAfter`` could not be cancelled. discord.py removes the listeners first, but a
        listener that it scheduled as a task before can still run afterwards: ``closed`` makes it
        start nothing.
        """
        self.closed = True
        notices = list(self.notices)
        for task in notices:
            task.cancel()
        await asyncio.gather(*notices, return_exceptions=True)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Check the guild and the owner once their members are known; fires per session."""
        self.check()

    def check(self) -> None:
        """Warn about a configured guild that the bot is not in and an owner who is not in it.

        With the members intent, discord.py fires ``on_ready`` once it cached the guilds' members;
        an unavailable guild (an outage) has none to look at. v3 checked nothing, and with its
        guild filter broken (B1), a wrong ``guild_id`` went unnoticed.
        """
        guild = self.bot.get_guild(self.config.guild_id)
        if guild is None:
            logger.warning(
                "TicketAwayNotice watches no channels: the bot is not in guild %s",
                self.config.guild_id,
            )
            return
        if not guild.unavailable and guild.get_member(self.config.user_id) is None:
            _not_a_member(guild, self.config.user_id)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """A new channel, of any kind: v3's ``ChannelCreateEvent``."""
        self.watch(channel)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """A new thread or forum post, which JDA's ``ChannelCreateEvent`` covered too.

        discord.py dispatches it for threads created since the bot connected only; a thread the
        bot joins is ``on_thread_join``.
        """
        self.watch(thread)

    def watch(self, channel: discord.abc.GuildChannel | discord.Thread) -> None:
        """Start a notice for ``channel`` if the config watches it and it takes messages.

        The guild and the name are read before anything waits. Categories and forums take no
        messages and are skipped; v3's ``asTextChannel()`` threw for every channel but a text
        channel (B2). The notice runs as a task, so the listener holds nothing up.
        """
        guild_id = channel.guild.id
        if self.closed or not self.config.watches(guild_id, channel.name):
            return
        if self._started_by_bot(channel):
            return
        target = _postable(channel)
        if target is None:
            logger.debug(
                "TicketAwayNotice skips %s (%s): it takes no messages", channel.name, channel.id
            )
            return
        task = asyncio.create_task(
            self._notice(guild_id, target), name=f"TicketAwayNotice notice {channel.id}"
        )
        self.notices.add(task)
        task.add_done_callback(self.notices.discard)

    def _started_by_bot(self, channel: discord.abc.GuildChannel | discord.Thread) -> bool:
        """Whether ``channel`` is a thread that the bot started, such as Ticket's archive.

        An archive thread takes the ticket channel's name, which may start with a prefix; v3 never
        posted in threads (B2). Channels carry no creator, and Ticket's tickets are meant to get the
        notice.
        """
        user = self.bot.user
        return (
            isinstance(channel, discord.Thread) and user is not None and channel.owner_id == user.id
        )

    async def _notice(self, guild_id: int, channel: Postable) -> None:
        """Run a notice; a failure that the plugin does not handle is logged with its traceback.

        Nothing awaits the task, so an exception left in it would be lost. Cancellation is no
        ``Exception`` and ends the task quietly.
        """
        try:
            await self._wait_and_post(guild_id, channel)
        except Exception:
            logger.exception(
                "TicketAwayNotice failed to post a notice in %s (%s)", channel.name, channel.id
            )

    async def _wait_and_post(self, guild_id: int, channel: Postable) -> None:
        """Post the notice in ``channel`` after the delay, if it is due before and after it.

        v3 checked the owner once and queued the message with ``queueAfter``, which nothing could
        cancel: it was posted into a channel deleted meanwhile, or after the owner came online.
        """
        if await self._due(guild_id, channel.id) is None:
            return
        await self.sleep(self.config.delay_millis / 1000)
        if (guild := await self._due(guild_id, channel.id)) is not None:
            await self._post(guild, channel)

    async def _due(self, guild_id: int, channel_id: int) -> discord.Guild | None:
        """The guild if the channel and the guild are still there and the owner is offline.

        discord.py drops a deleted channel, an archived thread and a left guild from its cache.
        Online, idle and do not disturb are not offline; invisible owners look offline to bots.
        """
        guild = self.bot.get_guild(guild_id)
        if guild is None or guild.get_channel_or_thread(channel_id) is None:
            return None
        member = await self._owner(guild)
        offline = member is not None and member.status is discord.Status.offline
        return guild if offline else None

    async def _owner(self, guild: discord.Guild) -> discord.Member | None:
        """The owner's member in ``guild``, or None with a warning when Discord has none.

        It comes from discord.py's cache, which the members and presences intents keep current,
        else from Discord, as v3's ``retrieveMemberById``: such a member has no presence, and
        discord.py says it is offline, as JDA did.
        """
        owner = self.config.user_id
        member = guild.get_member(owner)
        if member is not None:
            return member
        try:
            member = await guild.fetch_member(owner)
        except discord.NotFound:
            _not_a_member(guild, owner)
            return None
        except discord.HTTPException as error:
            logger.warning(
                "TicketAwayNotice cannot look up user %s in %s (%s): %s",
                owner,
                guild.name,
                guild.id,
                error,
            )
            return None
        return member

    async def _post(self, guild: discord.Guild, channel: Postable) -> None:
        """Post the ``not-online`` template in v3's zh-TW, with v3's global placeholders.

        v3 rendered it without a substitutor, which left the bot's ``bot_id`` and ``bot_name``. A
        notice that Discord refuses is a warning that names the channel and the guild.
        """
        template = self.templates.message(NOTICE, self.lang.default_locale)
        message = render_message(template, global_values(self.bot))
        try:
            await channel.send(
                content=message.content or None,
                embeds=message.embeds,
                view=message.view,
                files=message.files,
            )
        except discord.HTTPException as error:
            logger.warning(
                "TicketAwayNotice cannot post the notice in %s (%s) of %s (%s): %s",
                channel.name,
                channel.id,
                guild.name,
                guild.id,
                error,
            )


def check_notice(lang: Lang, templates: Templates) -> None:
    """Refuse a ``not-online`` template that the plugin can never post.

    The plugin gives no component IDs and no models, so a component with a ``uid`` or a
    ``model_key`` fails, as do a missing ``file_path`` and too many rows; v3 failed at each
    notice. The render has no placeholder values, and the files it opens are closed.

    Raises:
        ConfigError: The template cannot be posted; the error names its file.
    """
    locale = lang.default_locale
    try:
        message = render_message(templates.message(NOTICE, locale), {})
    except (TemplateError, ValueError) as error:
        msg = f"{lang.template(f'message/{NOTICE}', locale)}: cannot be posted: {error}"
        raise ConfigError(msg) from error
    for file in message.files:
        file.close()


def _not_a_member(guild: discord.Guild, owner: int) -> None:
    """Warn that the owner is not a member of the watched guild, so no notice is posted there."""
    logger.warning(
        "TicketAwayNotice posts no notice in %s (%s): user %s is not a member",
        guild.name,
        guild.id,
        owner,
    )


def _postable(channel: object) -> Postable | None:
    """``channel`` if it takes messages, typed by the call that the plugin makes.

    discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union.
    """
    return channel if isinstance(channel, Postable) else None
