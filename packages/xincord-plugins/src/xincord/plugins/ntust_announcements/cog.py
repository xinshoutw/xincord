"""The plugin's cog: the boards' loops, their posts and the ready check.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:15-95
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-43
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:117-153
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, override, runtime_checkable

import discord
from discord.ext import commands

from xincord.plugins.redaction import origin

from .config import bundled_review_prompt
from .conversion import Converter
from .store import Announcements, Posted
from .watch import Watcher
from .web import open_web

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from xincord.core.storage import Store

    from .api import Api
    from .config import Config
    from .store import Announcement
    from .watch import Sleep
    from .web import Page, Requests

type OpenWeb = Callable[[Api], AbstractAsyncContextManager[Requests]]  # settings to a session

FETCHES = 5  # NTUST pages fetched at a time, v3's maxConcurrentRequests
CROSS_MARK = "\N{CROSS MARK}"  # a reviewer's reaction that redoes a post
HOURGLASS = "\N{HOURGLASS WITH FLOWING SAND}"  # the bot's sign on the marked message during a redo
logger = logging.getLogger(__name__)


@runtime_checkable
class Postable(Protocol):
    """A channel that takes messages: text, announcement, voice and stage channels, threads.

    Categories and forum channels have no ``send``.
    """

    async def send(self, *, content: str | None = None) -> object:
        """Send a message to the channel."""
        ...


NO_MENTIONS = discord.AllowedMentions.none()  # the model's text pings nobody (v3: JDA's default)


class NtustAnnouncements(commands.Cog):
    """The plugin's state; ``setup`` adds it."""

    def __init__(self, bot: commands.Bot, config: Config, store: Store) -> None:
        """Keep the bot, the config and the store of the boards' posted lists.

        A reload builds a new cog from the new config: v3's reload kept the keys, the prompt and
        the interval that it had read first, and the model's settings were constants.
        """
        self.bot = bot
        self.config = config
        self.store = store
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # the boards' loops, from READY
        # The effects that tests replace: the waits, the clocks and the web.
        self.sleep: Sleep = asyncio.sleep
        self.clock: Callable[[], float] = time.monotonic
        self.now: Callable[[], datetime] = datetime.now  # the host's local time, as v3's
        self.open_web: OpenWeb = open_web
        self.watchers: dict[str, Watcher] = {}  # by board name, once the boards run
        self.redoing: set[str] = set()  # the URLs being redone
        self.redos: set[asyncio.Task[None]] = set()  # their tasks

    @override
    async def cog_load(self) -> None:
        """Start the boards' loops; they wait until the bot is ready.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is fetched before READY. In a ready bot, as after a reload, the boards pass at once: v3
        started its scheduler when it loaded, after JDA was ready, with no initial delay.
        """
        self.tasks = (asyncio.create_task(self._run(), name="NtustAnnouncements"),)
        if self.bot.is_ready():
            self.check()  # a plugin loaded into a ready bot gets no on_ready

    @override
    async def cog_unload(self) -> None:
        """Cancel the loops and wait for them, so that their session closes.

        A reload builds a new cog with the new config; v3's reload added a second scheduler to the
        first (duplicate posts) or failed after a disable.
        """
        tasks = (*self.tasks, *self.redos)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Check the boards' channels once the guilds are cached; fires for each session."""
        self.check()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Redo the announcement whose message a reviewer marked with a cross mark.

        Only ``reviewers``, the Unicode cross mark and the plugin's stored posts count; a second
        mark while the announcement is redone is ignored.
        """
        emoji = payload.emoji
        if payload.user_id not in self.config.reviewers or emoji.is_custom_emoji():
            return
        if emoji.name != CROSS_MARK:
            return
        announcement = await Announcements(self.store).find(payload.message_id)
        if announcement is None:
            return
        link = announcement.link
        watcher = self.watchers.get(link.board)
        if watcher is None or link.url in self.redoing:
            return
        self.redoing.add(link.url)
        logger.info(
            "NtustAnnouncements board %s: user %d marked %s; converting it again",
            link.board,
            payload.user_id,
            link.url,
        )
        marked = (payload.channel_id, payload.message_id)
        task = asyncio.create_task(self._redo(watcher, announcement, marked))
        self.redos.add(task)
        task.add_done_callback(self.redos.discard)

    async def _redo(
        self, watcher: Watcher, announcement: Announcement, marked: tuple[int, int]
    ) -> None:
        """Run the redo with an hourglass on the marked message, removed if the old post stays.

        A replaced post takes the marked message, and its hourglass, along. An unexpected error is
        logged with its traceback.
        """
        await self._sign(*marked, on=True)
        replaced = False
        try:
            replaced = await watcher.redo(announcement)
        except Exception:
            logger.exception("NtustAnnouncements: redoing %s failed", announcement.link.url)
        finally:
            self.redoing.discard(announcement.link.url)
        if not replaced:
            await self._sign(*marked, on=False)

    async def _sign(self, channel_id: int, message_id: int, *, on: bool) -> None:
        """Add the bot's hourglass to a marked message, or remove it; a refusal is a warning."""
        message = self.bot.get_partial_messageable(channel_id).get_partial_message(message_id)
        try:
            if on:
                await message.add_reaction(HOURGLASS)
            elif self.bot.user is not None:
                await message.remove_reaction(HOURGLASS, self.bot.user)
        except discord.HTTPException as error:
            logger.warning(
                "NtustAnnouncements: the hourglass on message %d of channel %d failed: %s",
                message_id,
                channel_id,
                error,
            )

    def check(self) -> None:
        """Warn about each board whose channel the bot cannot see or that takes no messages.

        v3 looked its guild up with ``!!`` when it started, which stopped the bot outside the
        owner's guild, and each channel when it first posted; a wrong ID now shows at READY, and
        when posting, as a warning. An unavailable guild (an outage) shows no channels either.
        """
        for board in self.config.boards:
            channel: object = self.bot.get_channel(board.channel_id)
            if channel is None:
                logger.warning(
                    "NtustAnnouncements board %s: the bot cannot see channel %d",
                    board.name,
                    board.channel_id,
                )
            elif not isinstance(channel, Postable):
                logger.warning(
                    "NtustAnnouncements board %s: channel %d takes no messages",
                    board.name,
                    board.channel_id,
                )

    async def _run(self) -> None:
        """Wait until the bot is ready, then run one loop per board over one session.

        Each board passes at once, then ``fetch-interval`` seconds after its own pass, so a board
        whose announcement waits hours between conversion attempts holds up no other; v3 ran all
        the boards in one cycle, five at a time, each holding its slot through the model's waits.
        The model's settings are the config's; the log names the endpoint by its origin only.
        """
        await self.bot.wait_until_ready()
        api = self.config.api
        logger.info(
            "NtustAnnouncements: converting articles with %s at %s (api-format %s)",
            api.model,
            origin(api.endpoint),
            api.format,
        )
        fetches = asyncio.Semaphore(FETCHES)
        async with self.open_web(api) as web:

            async def page(url: str) -> Page:
                async with fetches:  # held while fetching only
                    return await web.page(url)

            converter = Converter(
                self.config.api_keys,
                self.config.prompt,
                web.generate,
                self.sleep,
                self.clock,
                self.now,
                self.config.limits,
                (api.endpoint, api.url),
                reject=self.config.reject_texts,
                review_prompt=self.config.review_prompt or bundled_review_prompt(),
            )
            posted = Posted(self.store)
            announcements = Announcements(self.store)
            self.watchers = {
                board.name: Watcher(
                    board,
                    page,
                    converter.convert,
                    self._send,
                    posted,
                    review=converter.review,
                    delete=self._delete,
                    announcements=announcements,
                )
                for board in self.config.boards
            }
            async with asyncio.TaskGroup() as boards:
                for watcher in self.watchers.values():
                    boards.create_task(
                        watcher.run(self.config.fetch_interval, self.sleep), name=watcher.name
                    )

    async def _send(self, channel_id: int, content: str) -> int:
        """Post one message to a board's channel, which needs no cache, pinging nobody; its ID."""
        channel = self.bot.get_partial_messageable(channel_id)
        message = await channel.send(content=content, allowed_mentions=NO_MENTIONS)
        return message.id

    async def _delete(self, channel_id: int, message_id: int) -> None:
        """Delete one of the plugin's messages, which needs no cache."""
        channel = self.bot.get_partial_messageable(channel_id)
        await channel.get_partial_message(message_id).delete()
