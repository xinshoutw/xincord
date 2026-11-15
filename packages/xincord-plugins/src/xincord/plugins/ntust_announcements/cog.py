"""The plugin's cog: the feed's loop, its posts and the ready check."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, override, runtime_checkable

import discord
from discord.ext import commands

from xincord.plugins.redaction import origin

from .bulletin import open_bulletin
from .feed import Feed
from .state import States

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from xincord.core.storage import Store

    from .bulletin import Api
    from .config import Config
    from .feed import Sleep

type OpenBulletin = Callable[[str], AbstractAsyncContextManager[Api]]  # the API's URL to a session

logger = logging.getLogger(__name__)


@runtime_checkable
class Postable(Protocol):
    """A channel that takes messages: text, announcement, voice and stage channels, threads.

    Categories and forum channels have no ``send``.
    """

    async def send(self, *, content: str | None = None) -> object:
        """Send a message to the channel."""
        ...


NO_MENTIONS = discord.AllowedMentions.none()  # the rewrite's text pings nobody


def utc_now() -> datetime:
    """The time now, with its offset: the feed's events carry theirs."""
    return datetime.now(UTC)


class NtustAnnouncements(commands.Cog):
    """The plugin's state; ``setup`` adds it."""

    def __init__(self, bot: commands.Bot, config: Config, store: Store) -> None:
        """Keep the bot, the config and the store of the feed's state.

        A reload builds a new cog from the new config.
        """
        self.bot = bot
        self.config = config
        self.store = store
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # the feed's loop, from READY
        # The effects that tests replace: the waits, the clock and the web.
        self.sleep: Sleep = asyncio.sleep
        self.now: Callable[[], datetime] = utc_now
        self.open_bulletin: OpenBulletin = open_bulletin

    @override
    async def cog_load(self) -> None:
        """Start the feed's loop, which waits until the bot is ready; none without a channel.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is requested before READY. In a ready bot, as after a reload, the feed is read at once.
        """
        if len(self.config.placeholders) < len(self.config.boards):
            self.tasks = (asyncio.create_task(self._run(), name="NtustAnnouncements"),)
        if self.bot.is_ready():
            self.check()  # a plugin loaded into a ready bot gets no on_ready

    @override
    async def cog_unload(self) -> None:
        """Cancel the loop and wait for it, so that its session closes.

        A reload builds a new cog with the new config, whose loop replaces this one.
        """
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Check the boards' channels once the guilds are cached; fires for each session."""
        self.check()

    def check(self) -> None:
        """Name the boards without a channel, and warn about each channel the bot cannot see or
        that takes no messages.

        A wrong ID shows at READY, and when posting, as a warning. An unavailable guild (an outage)
        shows no channels either.
        """
        if placeholders := self.config.placeholders:
            logger.info(
                "NtustAnnouncements: %d boards have no channel yet: %s",
                len(placeholders),
                ", ".join(board.name for board in placeholders),
            )
        for board in self.config.boards:
            if not board.channel_id:
                continue
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
        """Wait until the bot is ready, then read the feed over one session until unloaded.

        The log names the API by its origin only.
        """
        await self.bot.wait_until_ready()
        config = self.config
        source = origin(config.api_url)
        logger.info("NtustAnnouncements: reading the feed at %s", source)
        async with self.open_bulletin(config.api_url) as api:
            feed = Feed(
                config.boards,
                api,
                self._send,
                States(self.store),
                config.rendition_wait,
                self.now,
                source,
            )
            await feed.run(config.poll_interval, self.sleep)

    async def _send(self, channel_id: int, content: str) -> int:
        """Post one message to a board's channel, which needs no cache, pinging nobody; its ID."""
        channel = self.bot.get_partial_messageable(channel_id)
        message = await channel.send(content=content, allowed_mentions=NO_MENTIONS)
        return message.id
