"""The alerts: v3's texts, their mentions and how often a channel hears about a course.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:94-138
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:51-76
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from xincord.core.i18n import Lang

    from .courses import Course
    from .store import Registered

type Pair = tuple[int, str]  # a channel and a course code


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
        """The channels to tell that ``code`` has seats at ``now``, then owed a full alert."""
        raise NotImplementedError

    def filled(self, code: str, channels: Iterable[int]) -> list[int]:
        """The channels owed a full alert about ``code``, which then are owed none."""
        raise NotImplementedError

    def keep(self, registered: Registered) -> None:
        """Forget the channels and courses that are no longer registered."""
        raise NotImplementedError


def escape(name: str) -> str:
    """A course's name for a Markdown link's text."""
    raise NotImplementedError


def available_posts(lang: Lang, course: Course, members: Sequence[int], second: int) -> list[Post]:
    """v3's available alert about ``course`` for ``members``, in the default locale."""
    raise NotImplementedError


def full_post(lang: Lang, course: Course) -> Post:
    """v3's full alert about ``course``, in the default locale; it pings nobody."""
    raise NotImplementedError
