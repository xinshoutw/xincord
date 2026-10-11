"""One step of the loop: the next registered course asked about, and its alerts.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:22-76
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:94-138
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .alerts import Alerts

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from xincord.core.i18n import Lang

    from .alerts import Post
    from .config import Config
    from .courses import Course
    from .store import Registrations

type Ask = Callable[[str, str], Awaitable[Course | None]]  # a semester and a code to a course
type Send = Callable[[int, Post], object]  # starts a post to a channel


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

    def __post_init__(self) -> None:
        """Measure the alerts' interval from the config."""
        self.alerts = Alerts(self.config.alert_interval)

    async def step(self) -> None:
        """Ask about the next registered course and post its alerts."""
        raise NotImplementedError
