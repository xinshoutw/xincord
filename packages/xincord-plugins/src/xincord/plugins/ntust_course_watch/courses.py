"""NTUST's course query: the request's body, the answer and v3's seats.

v3 asked for the whole catalogue of a semester (``CourseTeacher: " "``) and kept every course; the
plugin asks about one registered code at a time, since NTUST no longer answers the whole catalogue
(no answer in 60 seconds, then a 500 after 120, on 2026-10-11).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseApi.kt:16-92
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:51-67
"""

from dataclasses import dataclass


class AnswerError(Exception):
    """The course query's answer is not what the plugin reads."""


@dataclass(frozen=True)
class Course:
    """One course as the course query lists it."""

    code: str  # CourseNo
    name: str  # CourseName, in Chinese: the plugin asks in zh, as v3
    chosen: int  # ChooseStudent: the members who chose it
    limit: int  # Restrict2 as v3 read it

    @property
    def full(self) -> bool:
        """v3's ``isFull``: no seats left, a limit of 0 included."""
        raise NotImplementedError


def to_int_or_none(text: str) -> int | None:
    """Kotlin's ``String.toIntOrNull()``."""
    raise NotImplementedError


def request_text(semester: str, code: str) -> str:
    """The JSON body that asks about the courses whose code starts with ``code``."""
    raise NotImplementedError


def read_course(answer: object, code: str) -> Course | None:
    """The course ``code`` in the course query's parsed answer, or None when it lists none."""
    raise NotImplementedError
