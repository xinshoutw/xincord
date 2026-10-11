"""The loop's steps: the next registered course asked about and its alerts.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:22-76
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:94-138
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp
import pytest

from plugin_fakes import golden
from xincord.plugins.ntust_course_watch.alerts import Post
from xincord.plugins.ntust_course_watch.courses import AnswerError, Course
from xincord.plugins.ntust_course_watch.store import KEY, NAMESPACE
from xincord.plugins.ntust_course_watch.watch import Watcher
from xincord.plugins.ntust_course_watch.web import QueryError

if TYPE_CHECKING:
    from xincord.core.storage import Store
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch

type Answer = Course | Exception | None

GOLDEN = golden("ntust_course_watch")
NAME = GOLDEN["courses"]["CE162A001"]["name"]
SEATS = Course("CE162A001", NAME, 25, 60)
FULL = Course("CE162A001", NAME, 60, 60)
NOW = datetime(2026, 10, 11, 2, 0, 7, tzinfo=UTC)  # second 7, after v3's start


@dataclass
class Fakes:
    """The course query's answers per code (the last one repeats), the posts and the clocks."""

    answers: dict[str, list[Answer]] = field(default_factory=dict[str, list[Answer]])
    asked: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    posts: list[tuple[int, Post]] = field(default_factory=list[tuple[int, Post]])
    time: float = 1000.0  # the monotonic clock
    now: datetime = NOW

    async def ask(self, semester: str, code: str) -> Course | None:
        self.asked.append((semester, code))
        answers = self.answers.get(code, [None])
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

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
    cog: NtustCourseWatch, fakes: Fakes, answers: list[Answer]
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


FAILURES = "Failures are logged without flooding"


def lines(caplog: pytest.LogCaptureFixture, level: int, text: str) -> list[str]:
    """The log lines at ``level`` that hold ``text``."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == level and text in record.getMessage()
    ]


@pytest.mark.xfail(strict=True, reason=FAILURES)
async def test_failing_course_query(
    cog: NtustCourseWatch, fakes: Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Failures are logged without flooding."""
    await cog.registrations.add("CE162A001", 5, 1)
    fakes.answers["CE162A001"] = [*[QueryError(500)] * 4, FULL]
    watcher = fakes.watcher(cog)

    with caplog.at_level(logging.DEBUG):
        for _ in range(7):
            await watcher.step()

    # v3 printed every failure to stdout, about every 1.5 seconds.
    [warning] = lines(caplog, logging.WARNING, "code 500")
    assert "CE162A001" in warning
    assert len(lines(caplog, logging.DEBUG, "code 500")) == 3  # the rest of the episode
    [recovered] = lines(caplog, logging.INFO, "works again")
    assert "4 failures" in recovered
    assert len(fakes.asked) == 7


@pytest.mark.xfail(strict=True, reason=FAILURES)
async def test_kinds_of_failures(
    cog: NtustCourseWatch, fakes: Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Failures are logged without flooding."""
    await cog.registrations.add("CE162A001", 5, 1)
    errors: list[Answer] = [
        TimeoutError(),
        aiohttp.ClientConnectionError("Connection reset by peer"),
        AnswerError("the answer is not JSON"),
        QueryError(502),
    ]
    fakes.answers["CE162A001"] = [*errors, *errors, FULL]
    watcher = fakes.watcher(cog)

    with caplog.at_level(logging.WARNING):
        for _ in range(9):
            await watcher.step()

    # Each kind once per episode: a timeout, a connection error, an answer, a status.
    warnings = lines(caplog, logging.WARNING, "NTUST's course query")
    assert len(warnings) == 4
    assert "TimeoutError" in warnings[0]
    assert "Connection reset by peer" in warnings[1]
    assert "the answer is not JSON" in warnings[2]
    assert "code 502" in warnings[3]


@pytest.mark.xfail(strict=True, reason=FAILURES)
async def test_failed_check_keeps_the_state(cog: NtustCourseWatch, fakes: Fakes) -> None:
    """Requirement: Failures are logged without flooding."""
    await cog.registrations.add("CE162A001", 5, 1)
    fakes.answers["CE162A001"] = [SEATS, QueryError(500), FULL]
    watcher = fakes.watcher(cog)

    for _ in range(3):
        await watcher.step()

    # The course had seats at its last check that worked: it filled.
    assert [post.content for _, post in fakes.posts] == [
        GOLDEN["alerts"]["available"].replace("<@1> <@2>", "<@1>"),
        GOLDEN["alerts"]["full"],
    ]


@pytest.mark.xfail(strict=True, reason=FAILURES)
async def test_broken_document(
    cog: NtustCourseWatch, fakes: Fakes, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Failures are logged without flooding."""
    await store.put(NAMESPACE, KEY, ["not", "v3's", "document"])
    watcher = fakes.watcher(cog)

    with caplog.at_level(logging.INFO):
        await watcher.step()
        await watcher.step()
        await store.delete(NAMESPACE, KEY)
        await cog.registrations.add("CE162A001", 5, 1)
        for _ in range(3):
            await watcher.step()

    assert len(lines(caplog, logging.ERROR, "not v3's document")) == 1
    assert fakes.asked == [("1142", "CE162A001")] * 3  # nothing asked while it was broken
    assert len(lines(caplog, logging.INFO, "registrations read again")) == 1


@pytest.mark.xfail(strict=True, reason=FAILURES)
async def test_unexpected_error(
    cog: NtustCourseWatch, fakes: Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Failures are logged without flooding."""
    await cog.registrations.add("CE162A001", 5, 1)
    fakes.answers["CE162A001"] = [RuntimeError("broken"), SEATS]
    watcher = fakes.watcher(cog)

    await watcher.step()  # v3's loop died at an exception until the next reload
    await watcher.step()

    [record] = [record for record in caplog.records if "the step failed" in record.getMessage()]
    assert record.exc_info is not None
    assert len(fakes.posts) == 1
