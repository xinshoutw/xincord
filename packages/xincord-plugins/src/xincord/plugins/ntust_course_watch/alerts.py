"""The alerts: v3's texts, their mentions and how often a channel hears about a course."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .texts import MESSAGE_LIMIT, text, units

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from xincord.core.i18n import Lang

    from .courses import Course
    from .store import Registered

type Pair = tuple[int, str]  # a channel and a course code

MAX_USERS = 100  # Discord's limit for a message's allowed users
LINK_TEXT = re.compile(r"[\\\[\]]")  # what ends or breaks a Markdown link's text


@dataclass(frozen=True)
class Post:
    """One message to a channel, and the members whom it may ping."""

    content: str
    users: tuple[int, ...] = ()


@dataclass
class Alerts:
    """When each channel last heard that a course has seats, and the full alerts it is owed."""

    interval: float  # alert-interval: seconds between two available alerts to a channel
    last: dict[Pair, float] = field(default_factory=dict[Pair, float])
    owed: set[Pair] = field(default_factory=set[Pair])

    def seats(self, code: str, channels: Iterable[int], now: float) -> list[int]:
        """The channels to tell that ``code`` has seats at ``now``, then owed a full alert.

        A channel hears about a course at most once per ``interval``: v3 posted at every poll,
        about every 1.5 seconds, beyond Discord's rate limit, and JDA's queue grew without end.
        """
        due = [
            channel
            for channel in channels
            if (last := self.last.get((channel, code))) is None or now - last >= self.interval
        ]
        self.last = {**self.last, **{(channel, code): now for channel in due}}
        self.owed = self.owed | {(channel, code) for channel in due}
        return due

    def filled(self, code: str, channels: Iterable[int]) -> list[int]:
        """The channels owed a full alert about ``code``, which then are owed none.

        Only an available alert makes a channel owed one, so a course whose seats come and go
        faster than ``interval`` gives one full alert per available alert at most.
        """
        due = [channel for channel in channels if (channel, code) in self.owed]
        self.owed = self.owed - {(channel, code) for channel in due}
        return due

    def keep(self, registered: Registered) -> None:
        """Forget the channels and courses that are no longer registered."""
        kept = {(channel, code) for code, channels in registered.items() for channel in channels}
        self.last = {pair: time for pair, time in self.last.items() if pair in kept}
        self.owed = self.owed & kept


def escape(name: str) -> str:
    """A course's name for a Markdown link's text: ``\\``, ``[`` and ``]`` escaped.

    v3 inserted the name as it was, and a ``]`` ended the link's text.
    """
    return LINK_TEXT.sub(lambda found: f"\\{found.group()}", name)


def _available(lang: Lang, course: Course, members: Sequence[int], second: int) -> str:
    values = {
        "ncw@second": str(second),
        "ncw@mentions": " ".join(f"<@{member}>" for member in members),
        "ncw@course_name": escape(course.name),
        "ncw@course_id": course.code,
    }
    return text(lang, "alert.available", lang.default_locale, values)


def available_posts(lang: Lang, course: Course, members: Sequence[int], second: int) -> list[Post]:
    """v3's available alert about ``course`` for ``members``, in the default locale.

    v3's text: ``second`` (v3's ``now.second``), the members' mentions in a spoiler, which still
    pings them, the course's name in a link to the course selection and its code in a code block.
    Mentions that do not fit in one message (2000 UTF-16 code units, 100 allowed users) go on in
    further posts: JDA refused v3's message by throwing in its loop.
    """
    posts: list[Post] = []
    group: tuple[int, ...] = ()
    for member in members:
        wider = (*group, member)
        if group and (
            len(wider) > MAX_USERS or units(_available(lang, course, wider, second)) > MESSAGE_LIMIT
        ):
            posts.append(Post(_available(lang, course, group, second), group))
            wider = (member,)
        group = wider
    return [*posts, Post(_available(lang, course, group, second), group)]


def full_post(lang: Lang, course: Course) -> Post:
    """v3's full alert about ``course``, in the default locale; it pings nobody.

    v3 passed the members to ``mentionUsers``, but its text mentioned none of them.
    """
    values = {"ncw@course_name": escape(course.name), "ncw@course_id": course.code}
    return Post(text(lang, "alert.full", lang.default_locale, values))
