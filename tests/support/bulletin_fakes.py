"""bulletin, the channels and the clock for the feed's tests, and a feed over them.

``World`` holds a fake API whose events and announcements the tests add, channels that record or
refuse posts, and a clock that the tests move; each ``feed()`` is a new plugin run over the same
store, as after a restart.
"""

import itertools
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from xincord.plugins.ntust_announcements.bulletin import (
    PAGE,
    Announcement,
    Attachment,
    Event,
    Events,
    Item,
    Rendition,
)
from xincord.plugins.ntust_announcements.config import Board
from xincord.plugins.ntust_announcements.feed import Feed
from xincord.plugins.ntust_announcements.state import States

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xincord.core.storage import Store

NOW = datetime(2026, 11, 16, 1, 0, tzinfo=UTC)
WAIT = 3600.0
ORIGIN = "https://bulletin.example.org"
DORMITORY_KEY = "1053-1436"


def board(name: str, key: str, channel: int, prefix: str = "") -> Board:
    """A configured board; the config's own tests validate the fields."""
    return Board.model_construct(name=name, board=key, channel_id=channel, title_prefix=prefix)


DORMITORY = board("STUDENT_DORMITORY", DORMITORY_KEY, 101)


def article_url(number: int) -> str:
    """The school's URL of the announcement ``number``."""
    return f"https://student.ntust.edu.tw/p/406-1053-{number},r1436.php"


@dataclass
class FakeApi:
    """bulletin's feed and announcements; ``error`` fails every feed read, ``failing`` the reads
    of the announcements it names."""

    log: list[Event] = field(default_factory=list[Event])
    announcements: dict[int, Announcement] = field(default_factory=dict[int, Announcement])
    error: Exception | None = None
    failing: dict[int, Exception] = field(default_factory=dict[int, Exception])
    reads: list[int] = field(default_factory=list[int])  # the `after` of each feed read
    asked: list[int] = field(default_factory=list[int])  # the announcements read

    def add(self, kind: str, number: int, *, notify: bool = False, at: datetime = NOW) -> Event:
        """Record an event for the announcement ``number``, which must exist."""
        found = self.announcements[number]
        item = Item.model_validate(found.model_dump(exclude={"attachments"}))
        event = Event(id=len(self.log) + 1, kind=kind, notify=notify, at=at, announcement=item)
        self.log.append(event)
        return event

    def publish(  # noqa: PLR0913 - an announcement's fields
        self,
        number: int,
        *,
        notify: bool = True,
        at: datetime = NOW,
        boards: Sequence[str] = (DORMITORY_KEY,),
        title: str = "Dormitory notice",
        link_item: bool = False,
        markdown: str | None = None,
        attachments: Sequence[tuple[str, str]] = (),
    ) -> Event:
        """Add the announcement ``number`` and its `published` event."""
        self.announcements[number] = Announcement(
            id=number,
            url=article_url(number),
            link_item=link_item,
            title=title,
            boards=tuple(boards),
            rendition=None if markdown is None else Rendition(markdown=markdown),
            attachments=tuple(Attachment(name=name, url=url) for name, url in attachments),
        )
        return self.add("published", number, notify=notify, at=at)

    def render(self, number: int, markdown: str, *, at: datetime = NOW) -> Event:
        """Give the announcement ``number`` a rewrite, and record its `rendered` event."""
        rewritten = Rendition(markdown=markdown)
        self.announcements[number] = self.announcements[number].model_copy(
            update={"rendition": rewritten}
        )
        return self.add("rendered", number, at=at)

    async def events(self, after: int) -> Events:
        self.reads.append(after)
        if self.error is not None:
            raise self.error
        page = tuple(event for event in self.log if event.id > after)[:PAGE]
        return Events(events=page, last=page[-1].id if page else after)

    async def announcement(self, announcement_id: int) -> Announcement | None:
        self.asked.append(announcement_id)
        if (error := self.failing.get(announcement_id)) is not None:
            raise error
        return self.announcements.get(announcement_id)


@dataclass
class Channels:
    """The channels: each post is recorded, except in a channel that ``refusing`` names, or once
    a channel has taken as many messages as ``taking`` gives it."""

    sent: list[tuple[int, str]] = field(default_factory=list[tuple[int, str]])
    refusing: dict[int, Exception] = field(default_factory=dict[int, Exception])
    taking: dict[int, int] = field(default_factory=dict[int, int])
    ids: itertools.count[int] = field(default_factory=lambda: itertools.count(1000))

    async def post(self, channel: int, content: str) -> int:
        if (error := self.refusing.get(channel)) is not None:
            raise error
        if len(self.got(channel)) >= self.taking.get(channel, len(self.sent) + 1):
            msg = "connection reset"
            raise OSError(msg)
        self.sent.append((channel, content))
        return next(self.ids)

    def got(self, channel: int) -> list[str]:
        """The messages that ``channel`` got."""
        return [content for to, content in self.sent if to == channel]


@dataclass
class Clock:
    """The wall clock, which tests move."""

    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


@dataclass
class World:
    """The fakes and the store that each run of the feed shares."""

    store: Store
    boards: tuple[Board, ...] = (DORMITORY,)
    api: FakeApi = field(default_factory=FakeApi)
    channels: Channels = field(default_factory=Channels)
    clock: Clock = field(default_factory=Clock)

    @property
    def states(self) -> States:
        return States(self.store)

    def feed(self) -> Feed:
        """A new run of the plugin's feed, as after a restart."""
        return Feed(
            self.boards,
            self.api,
            self.channels.post,
            self.states,
            WAIT,
            self.clock.now,
            ORIGIN,
        )
