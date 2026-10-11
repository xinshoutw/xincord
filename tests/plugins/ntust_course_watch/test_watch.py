"""The loop's steps: the next registered course asked about and its alerts.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:22-76
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:94-138
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import golden
from xincord.plugins.ntust_course_watch.alerts import Post
from xincord.plugins.ntust_course_watch.courses import Course
from xincord.plugins.ntust_course_watch.watch import Watcher

if TYPE_CHECKING:
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch

GOLDEN = golden("ntust_course_watch")
NAME = GOLDEN["courses"]["CE162A001"]["name"]
SEATS = Course("CE162A001", NAME, 25, 60)
FULL = Course("CE162A001", NAME, 60, 60)
NOW = datetime(2026, 10, 11, 2, 0, 7, tzinfo=UTC)  # second 7, after v3's start


@dataclass
class Fakes:
    """The course query's answers per code (the last one repeats), the posts and the clocks."""

    answers: dict[str, list[Course | None]] = field(default_factory=dict[str, list[Course | None]])
    asked: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    posts: list[tuple[int, Post]] = field(default_factory=list[tuple[int, Post]])
    time: float = 1000.0  # the monotonic clock
    now: datetime = NOW

    async def ask(self, semester: str, code: str) -> Course | None:
        self.asked.append((semester, code))
        answers = self.answers.get(code, [None])
        return answers.pop(0) if len(answers) > 1 else answers[0]

    def send(self, channel: int, post: Post) -> None:
        self.posts.append((channel, post))

    def watcher(self, cog: NtustCourseWatch) -> Watcher:
        """A watcher over the loaded plugin's config, texts and registrations."""
        return Watcher(
            cog.config,
            cog.lang,
            cog.registrations,
            self.ask,
            self.send,
            lambda: self.now,
            lambda: self.time,
        )


@pytest.fixture
def fakes() -> Fakes:
    """The course query, the posts and the clocks of a watcher."""
    return Fakes()


async def test_seats(cog: NtustCourseWatch, fakes: Fakes) -> None:
    """Requirement: Channels hear about courses with seats."""
    await cog.registrations.add("CE162A001", 5, 1)
    await cog.registrations.add("CE162A001", 5, 2)
    await cog.registrations.add("CE162A001", 6, 3)
    fakes.answers["CE162A001"] = [SEATS]
    watcher = fakes.watcher(cog)

    await watcher.step()

    assert fakes.asked == [("1142", "CE162A001")]  # the bundled semester, v3's
    assert fakes.posts == [
        (5, Post(GOLDEN["alerts"]["available"], (1, 2))),
        (6, Post(GOLDEN["alerts"]["available"].replace("<@1> <@2>", "<@3>"), (3,))),
    ]


async def test_seats_again(cog: NtustCourseWatch, fakes: Fakes) -> None:
    """Requirement: Channels hear about courses with seats."""
    await cog.registrations.add("CE162A001", 5, 1)
    fakes.answers["CE162A001"] = [SEATS]
    watcher = fakes.watcher(cog)

    await watcher.step()
    fakes.time += 59.0
    await watcher.step()  # v3 posted at every poll, every 1.5 seconds
    assert len(fakes.posts) == 1
    fakes.time += 1.0
    await watcher.step()

    assert [channel for channel, _ in fakes.posts] == [5, 5]


async def test_became_full(cog: NtustCourseWatch, fakes: Fakes) -> None:
    """Requirement: Channels hear once when a course fills."""
    await cog.registrations.add("CE162A001", 5, 1)
    fakes.answers["CE162A001"] = [SEATS, FULL]
    watcher = fakes.watcher(cog)

    await watcher.step()
    await watcher.step()
    await watcher.step()  # still full: nothing more

    assert fakes.posts[1:] == [(5, Post(GOLDEN["alerts"]["full"], ()))]


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param([FULL], id="full"),
        pytest.param([None, FULL], id="unknown, then full"),
        pytest.param([None], id="unknown"),
    ],
)
async def test_full_at_the_first_check(
    cog: NtustCourseWatch, fakes: Fakes, answers: list[Course | None]
) -> None:
    """Requirement: Channels hear once when a course fills."""
    await cog.registrations.add("CE162A001", 5, 1)
    fakes.answers["CE162A001"] = answers
    watcher = fakes.watcher(cog)

    await watcher.step()
    await watcher.step()

    assert fakes.posts == []


async def test_full_after_another_channel_registered(cog: NtustCourseWatch, fakes: Fakes) -> None:
    """Requirement: Channels hear once when a course fills."""
    await cog.registrations.add("CE162A001", 5, 1)
    fakes.answers["CE162A001"] = [SEATS, FULL]
    watcher = fakes.watcher(cog)

    await watcher.step()
    await cog.registrations.add("CE162A001", 6, 2)  # after the available alert
    await watcher.step()

    assert [channel for channel, _ in fakes.posts] == [5, 5]  # 6 heard nothing about the seats
