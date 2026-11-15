"""The feed's passes: new announcements on the configured boards, posted once per channel.

Each pass reads the events after the stored position, puts the notify-worthy announcements of the
configured boards in waiting, and posts those that are due: rewritten, or waited for long enough.
"""

import logging
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import TYPE_CHECKING

import aiohttp
import discord

from xincord.plugins.failures import Failures

from .bulletin import PAGE, AnswerError, FetchError
from .messages import announcement_messages
from .state import DataError, State, Waiting

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from .bulletin import Api, Event, Events, Item
    from .config import Board
    from .state import States

type Post = Callable[[int, str], Awaitable[object]]  # one message to a channel
type Sleep = Callable[[float], Awaitable[object]]

logger = logging.getLogger(__name__)

NAME = "NtustAnnouncements"
GIVE_UP = timedelta(days=1)  # how long after it was due an announcement is still tried
# A read that did not work: a status, a body of another shape, aiohttp's errors and OSError,
# timeouts included.
READ_ERRORS = (FetchError, AnswerError, aiohttp.ClientError, OSError)
# A post that Discord refused or that did not reach it.
POST_ERRORS = (discord.HTTPException, aiohttp.ClientError, OSError)


def _kind(error: Exception) -> object:
    """What a failure episode counts: a status code, else the error's type."""
    if isinstance(error, FetchError):
        return error.status
    if isinstance(error, discord.HTTPException):
        return error.status
    return type(error)


def _describe(error: Exception) -> str:
    """How a log line ends for a failed read."""
    if isinstance(error, FetchError):
        return f"answered with {error}"
    if isinstance(error, AnswerError):
        return f"gave an unexpected answer: {error}"
    return f"failed: {str(error) or type(error).__name__}"


def _with(state: State, entry: Waiting) -> State:
    """``state`` with ``entry`` in place of the waiting announcement of its ID."""
    waiting = tuple(entry if other.id == entry.id else other for other in state.waiting)
    return replace(state, waiting=waiting)


def _without(state: State, announcement: int) -> State:
    """``state`` without the waiting announcement ``announcement``."""
    return replace(state, waiting=tuple(w for w in state.waiting if w.id != announcement))


@dataclass
class Feed:
    """The configured boards and the plugin's effects: the API, the channels and the store."""

    boards: tuple[Board, ...]
    api: Api
    post: Post
    states: States
    wait: float  # seconds an announcement waits for its rewrite
    now: Callable[[], datetime]
    origin: str  # how the logs name the API
    state: State | None = None  # the truth while the plugin runs, once read
    saved: State | None = None  # what the store holds, as far as the plugin knows
    # Failure episodes, each kind logged once: the feed's reads, the announcements' reads, the
    # posts, the stored document and its writes.
    reads: Failures = field(default_factory=Failures)
    items: Failures = field(default_factory=Failures)
    posts: Failures = field(default_factory=Failures)
    document: Failures = field(default_factory=Failures)
    writes: Failures = field(default_factory=Failures)

    async def run(self, interval: float, sleep: Sleep) -> None:
        """Pass at once, then ``interval`` seconds after each pass, until cancelled."""
        while True:
            await self.check()
            await sleep(interval)

    async def check(self) -> None:
        """One pass: read the new events, then post the announcements that are due.

        Any unexpected error is logged with its traceback, and the next pass comes as usual;
        cancellation (an unload) ends the pass at once.
        """
        try:
            await self._pass()
        except Exception:
            logger.exception("%s: the pass failed", NAME)

    async def _pass(self) -> None:
        state = self.state
        if state is None:
            state = await self._load()
            if state is None:
                return
        state = await self._read(state)
        state = await self._post_due(state)
        await self._keep(state)

    async def _load(self) -> State | None:
        """The stored state; None when it is broken (logged) or at the first read.

        The first read finds the feed's end and stores it, posting nothing.
        """
        try:
            stored = await self.states.load()
        except DataError as error:
            logger.log(
                logging.ERROR if self.document.fail(DataError) else logging.DEBUG,
                "%s: the feed's stored state is broken, so nothing is read or posted until "
                "the document is fixed or deleted: %s",
                NAME,
                error,
            )
            return None
        if stored is not None:
            self.state = self.saved = stored
            return stored
        end = State(0)
        while (page := await self._page(end.after)) is not None:
            end = State(page.last)
            if len(page.events) < PAGE:
                logger.info(
                    "%s: starting after event %d of the feed at %s", NAME, end.after, self.origin
                )
                self._read_again()
                await self._keep(end)
                break
        return None

    async def _page(self, after: int) -> Events | None:
        """The events after ``after``, or None when the read failed (logged)."""
        try:
            return await self.api.events(after)
        except READ_ERRORS as error:
            logger.log(
                logging.WARNING if self.reads.fail(_kind(error)) else logging.DEBUG,
                "%s: the feed at %s %s",
                NAME,
                self.origin,
                _describe(error),
            )
            return None

    def _read_again(self) -> None:
        if failed := self.reads.succeed():
            logger.info(
                "%s: the feed at %s works again after %d failures", NAME, self.origin, failed
            )

    async def _read(self, state: State) -> State:
        """``state`` after the events that follow its position, kept after each read."""
        while (page := await self._page(state.after)) is not None:
            for event in page.events:
                state = self._handle(state, event)
            state = replace(state, after=page.last)
            await self._keep(state)
            if len(page.events) < PAGE:
                self._read_again()
                break
        return state

    def _handle(self, state: State, event: Event) -> State:
        """``state`` after ``event``: a new announcement waits, a rewrite makes it due."""
        waiting = {entry.id: entry for entry in state.waiting}
        item = event.announcement
        entry = waiting.get(item.id)
        if event.kind == "published" and event.notify and entry is None and self._channels(item):
            # A link entry is never rewritten.
            due = event.at if item.link_item else event.at + timedelta(seconds=self.wait)
            waiting[item.id] = Waiting(item.id, due)
            logger.info("%s: announcement %d waits until %s", NAME, item.id, due.isoformat())
        elif event.kind == "rendered" and entry is not None:
            waiting[item.id] = replace(entry, due=min(entry.due, event.at))
        elif event.kind == "withdrawn" and entry is not None:
            del waiting[item.id]
            logger.info("%s: announcement %d was withdrawn before it was posted", NAME, item.id)
        return replace(state, waiting=tuple(waiting.values()))

    def _channels(self, item: Item) -> list[int]:
        """The channels of the configured boards that ``item`` is on, in config order, once each."""
        channels: list[int] = []
        for board in self.boards:
            if (
                board.channel_id
                and board.channel_id not in channels
                and board.matches(item.boards)
                and item.title.startswith(board.title_prefix)
            ):
                channels.append(board.channel_id)
        return channels

    async def _post_due(self, state: State) -> State:
        """``state`` after posting each announcement that is due, in the order they came."""
        now = self.now()
        for entry in state.waiting:
            if entry.due <= now:
                state = await self._deliver(state, entry, now)
        return state

    async def _deliver(self, state: State, entry: Waiting, now: datetime) -> State:
        """``state`` after posting ``entry`` to each of its channels that has not got it.

        The announcement is read again, so that its rewrite and its boards are the latest. Each
        channel that takes it is kept at once; the others try again at the next pass.
        """
        try:
            found = await self.api.announcement(entry.id)
        except READ_ERRORS as error:
            logger.log(
                logging.WARNING if self.items.fail(_kind(error)) else logging.DEBUG,
                "%s: announcement %d at %s %s; it is read again at the next pass",
                NAME,
                entry.id,
                self.origin,
                _describe(error),
            )
            return self._retried(state, entry, now, "could not be read")
        if failed := self.items.succeed():
            logger.info(
                "%s: announcements at %s read again after %d failures", NAME, self.origin, failed
            )
        if found is None:
            logger.warning(
                "%s: announcement %d is gone from %s, so it is not posted",
                NAME,
                entry.id,
                self.origin,
            )
            return _without(state, entry.id)
        messages = announcement_messages(found)
        refused: list[int] = []
        for channel in self._channels(found):
            if channel in entry.posted:
                continue
            if await self._send(channel, entry.id, messages):
                entry = replace(entry, posted=(*entry.posted, channel))
                state = _with(state, entry)
                await self._keep(state)
            else:
                refused.append(channel)
        if not refused:
            return _without(state, entry.id)
        channels = ", ".join(str(channel) for channel in refused)
        return self._retried(state, entry, now, f"was refused by channel {channels}")

    def _retried(self, state: State, entry: Waiting, now: datetime, failure: str) -> State:
        """``state`` with ``entry`` for the next pass, or without it a day after it was due."""
        if now - entry.due < GIVE_UP:
            return _with(state, entry)
        logger.error(
            "%s: announcement %d %s for a day after it was due, so it is dropped",
            NAME,
            entry.id,
            failure,
        )
        return _without(state, entry.id)

    async def _send(self, channel: int, announcement: int, messages: list[str]) -> bool:
        """Send the messages in order; whether the channel counts as having the announcement.

        A refused first message posted nothing, and the channel waits for the next pass. A refused
        later one leaves the start posted: posting it again would repeat it, so it counts as
        posted, with an error.
        """
        for number, message in enumerate(messages, start=1):
            try:
                await self.post(channel, message)
            except POST_ERRORS as error:
                text = str(error) or type(error).__name__
                if number > 1:
                    logger.error(  # noqa: TRY400 - Discord's answer, not a traceback, says why
                        "%s: channel %d refused part %d of %d of announcement %d, so the rest is "
                        "not posted: %s",
                        NAME,
                        channel,
                        number,
                        len(messages),
                        announcement,
                        text,
                    )
                    return True
                logger.log(
                    logging.WARNING if self.posts.fail(_kind(error)) else logging.DEBUG,
                    "%s: channel %d refused announcement %d: %s",
                    NAME,
                    channel,
                    announcement,
                    text,
                )
                return False
        if failed := self.posts.succeed():
            logger.info("%s: the channels take the posts again after %d refusals", NAME, failed)
        logger.info("%s: posted announcement %d to channel %d", NAME, announcement, channel)
        return True

    async def _keep(self, state: State) -> None:
        """Hold ``state``, and store it unless the store has it; a refused write is logged.

        The held state is the truth while the plugin runs, so a refused write posts nothing
        twice; a later pass stores it.
        """
        self.state = state
        if state == self.saved:
            return
        try:
            await self.states.save(state)
        except sqlite3.Error as error:
            logger.log(
                logging.WARNING if self.writes.fail(type(error)) else logging.DEBUG,
                "%s: the feed's state was not stored; it is stored at the next pass: %s",
                NAME,
                error,
            )
            return
        self.saved = state
        if failed := self.writes.succeed():
            logger.info("%s: the feed's state is stored again after %d failures", NAME, failed)
