"""The listeners that post the away notice in new ticket channels while the owner is offline.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:11-39
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:26-29
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import discord
from discord.ext import commands

from xincord.core.placeholders import global_values
from xincord.core.templates import render_message

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
        if not self.config.watches(guild_id, channel.name):
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

    async def _notice(self, guild_id: int, channel: Postable) -> None:
        """Post the notice in ``channel`` after the delay, if it is due before and after it.

        v3 checked the owner once and queued the message with ``queueAfter``, which nothing could
        cancel: it was posted into a channel deleted meanwhile, or after the owner came online.
        """
        if not await self._due(guild_id, channel.id):
            return
        await self.sleep(self.config.delay_millis / 1000)
        if await self._due(guild_id, channel.id):
            await self._post(channel)

    async def _due(self, guild_id: int, channel_id: int) -> bool:
        """Whether the channel and its guild are still there and the owner is offline.

        discord.py drops a deleted channel, an archived thread and a left guild from its cache.
        The owner comes from the cache, which the members and presences intents keep current,
        else from Discord, as v3's ``retrieveMemberById``: such a member has no presence, and
        discord.py says it is offline, as JDA did. Online, idle and do not disturb are not.
        """
        guild = self.bot.get_guild(guild_id)
        if guild is None or guild.get_channel_or_thread(channel_id) is None:
            return False
        owner = self.config.user_id
        member = guild.get_member(owner) or await guild.fetch_member(owner)
        return member.status is discord.Status.offline

    async def _post(self, channel: Postable) -> None:
        """Post the ``not-online`` template in v3's zh-TW, with v3's global placeholders.

        v3 rendered it without a substitutor, which left the bot's ``bot_id`` and ``bot_name``.
        """
        template = self.templates.message(NOTICE, self.lang.default_locale)
        message = render_message(template, global_values(self.bot))
        await channel.send(
            content=message.content or None,
            embeds=message.embeds,
            view=message.view,
            files=message.files,
        )


def _postable(channel: object) -> Postable | None:
    """``channel`` if it takes messages, typed by the call that the plugin makes.

    discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union.
    """
    return channel if isinstance(channel, Postable) else None
