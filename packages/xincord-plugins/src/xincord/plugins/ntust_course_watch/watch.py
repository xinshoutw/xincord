"""One step of the loop: the next registered course asked about, and its alerts.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:22-76
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:94-138
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp

from xincord.plugins.failures import Failures

from .alerts import Alerts, available_posts, full_post
from .courses import AnswerError
from .store import DataError
from .web import QueryError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping
    from datetime import datetime

    from xincord.core.i18n import Lang

    from .alerts import Post
    from .config import Config
    from .courses import Course
    from .store import Registered, Registrations

type Ask = Callable[[str, str], Awaitable[Course | None]]  # a semester and a code to a course
type Send = Callable[[int, Post], object]  # starts a post to a channel

logger = logging.getLogger(__name__)

# A request that did not get an answer: aiohttp's errors and OSError, timeouts included.
NETWORK_ERRORS = (aiohttp.ClientError, OSError)


def describe(error: BaseException) -> str:
    """The error's message, or its type when it has none (aiohttp's timeouts have none)."""
    return str(error) or type(error).__name__


@dataclass
class Watcher:
    """The registered courses' states and their effects: the course query, the posts, the clocks."""

    config: Config
    lang: Lang
    registrations: Registrations
    ask: Ask
    send: Send
    now: Callable[[], datetime]  # aware: the start is compared with it
    clock: Callable[[], float]  # monotonic: the alerts' interval is measured with it
    alerts: Alerts = field(init=False)
    courses: dict[str, Course] = field(default_factory=dict[str, "Course"])  # at their last check
    cursor: str | None = None  # the code asked about last
    # Failure episodes of the course query and of the registrations document: each kind of
    # failure is logged once per episode (v3 printed every failure to stdout).
    queries: Failures = field(default_factory=Failures)
    document: Failures = field(default_factory=Failures)

    def __post_init__(self) -> None:
        """Measure the alerts' interval from the config."""
        self.alerts = Alerts(self.config.alert_interval)

    async def step(self) -> None:
        """Ask about the next registered course and post its alerts: v3's poll, for one course.

        Before ``start``, or while nothing is registered, nothing is asked and the states are
        forgotten, so that the first check afterwards alerts as v3's first poll did; v3 polled the
        whole catalogue all the time. The codes are asked about in turn, in sorted order. Any
        unexpected error is logged with its traceback and the next step comes as usual: v3's loop
        died at the first exception until the next reload. Cancellation ends the step at once.
        """
        try:
            await self._step()
        except Exception:
            logger.exception("NtustCourseWatch: the step failed")

    async def _step(self) -> None:
        if self.now() < self.config.start:
            self._forget()
            return
        registered = await self._registered()
        if not registered:
            self._forget()
            return
        code = _next(registered, self.cursor)
        self.cursor = code
        try:
            course = await self.ask(self.config.semester, code)
        except QueryError as error:
            self._failed(error.status, code, str(error))
            return
        except AnswerError as error:
            self._failed(AnswerError, code, str(error))
            return
        except NETWORK_ERRORS as error:
            self._failed(type(error), code, describe(error))
            return
        if failed := self.queries.succeed():
            logger.info(
                "NtustCourseWatch: NTUST's course query works again after %d failures", failed
            )
        self._keep(registered)
        previous = self.courses.pop(code, None)
        if course is None:  # NTUST lists no such course: as v3, which kept the listed ones
            return
        self.courses[code] = course
        channels = registered[code]
        if not course.full:
            self._seats(course, channels)
        elif previous is not None and not previous.full:
            self._filled(course, channels)

    async def _registered(self) -> Registered | None:
        """The registrations, or None when their document is broken (logged)."""
        try:
            registered = await self.registrations.load()
        except DataError as error:
            logger.log(
                logging.ERROR if self.document.fail(DataError) else logging.DEBUG,
                "NtustCourseWatch: the registrations are not v3's document, so no course is "
                "checked until it is fixed or deleted: %s",
                error,
            )
            return None
        if self.document.succeed():
            logger.info("NtustCourseWatch: the registrations read again")
        return registered

    def _failed(self, kind: object, code: str, detail: str) -> None:
        """Log a failed request: once per kind of failure and episode, the rest at debug level.

        The course keeps its state from its last check, and the next step asks about the next
        code.
        """
        logger.log(
            logging.WARNING if self.queries.fail(kind) else logging.DEBUG,
            "NtustCourseWatch: NTUST's course query about %s failed: %s",
            code,
            detail,
        )

    def _seats(self, course: Course, channels: Mapping[int, tuple[int, ...]]) -> None:
        """v3's available alert to the channels that have not heard about it lately."""
        second = self.now().second
        for channel in self.alerts.seats(course.code, channels, self.clock()):
            for post in available_posts(self.lang, course, channels[channel], second):
                self.send(channel, post)

    def _filled(self, course: Course, channels: Mapping[int, tuple[int, ...]]) -> None:
        """v3's full alert to the channels that heard about its seats."""
        for channel in self.alerts.filled(course.code, channels):
            self.send(channel, full_post(self.lang, course))

    def _keep(self, registered: Registered) -> None:
        """Forget the states of the courses and channels that are no longer registered."""
        self.courses = {code: self.courses[code] for code in self.courses if code in registered}
        self.alerts.keep(registered)

    def _forget(self) -> None:
        self.courses = {}
        self.alerts = Alerts(self.config.alert_interval)
        self.cursor = None


def _next(registered: Registered, cursor: str | None) -> str:
    """The registered code after ``cursor`` in sorted order, the first one after the last."""
    codes = sorted(registered)
    return next((code for code in codes if cursor is None or code > cursor), codes[0])
