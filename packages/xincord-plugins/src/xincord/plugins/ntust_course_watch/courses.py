"""NTUST's course query: the request's body, the answer and v3's seats.

v3 asked for the whole catalogue of a semester (``CourseTeacher: " "``) and kept every course; the
plugin asks about one registered code at a time, since NTUST no longer answers the whole catalogue
(no answer in 60 seconds, then a 500 after 120, on 2026-10-11).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseApi.kt:16-92
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:51-67
"""

import json
import re
from dataclasses import dataclass
from typing import cast

# Kotlin's toIntOrNull(): an optional sign and decimal digits of any script, within an Int.
INT = re.compile(r"[+-]?\d+")
INT_MIN, INT_MAX = -(2**31), 2**31 - 1
LANGUAGE = "zh"  # course names in Chinese, as v3 asked


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
        """v3's ``isFull``: no seats left, so a limit of 0 (or text) is always full."""
        return self.chosen >= self.limit


def to_int_or_none(text: str) -> int | None:
    """Kotlin's ``String.toIntOrNull()``: a sign and decimal digits of any script within an Int.

    Python refuses to convert more than 4,300 digits, far beyond an Int unless they are zeros.
    """
    if INT.fullmatch(text) is None:
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return number if INT_MIN <= number <= INT_MAX else None


def request_text(semester: str, code: str) -> str:
    """The JSON body that asks about the courses whose code starts with ``code``.

    The course query site's body (``app.cbe19373.js``, 2026-10-11), in its order, with the API's
    own spelling ``OnleyNTUST``; v3 sent ``CourseTeacher: " "`` and no code to get every course.
    """
    body: dict[str, object] = {
        "Semester": semester,
        "CourseNo": code,
        "CourseName": "",
        "CourseTeacher": "",
        "Dimension": "",
        "CourseNotes": "",
        "CampusNotes": "",
        "ForeignLanguage": 0,
        "OnlyIntensive": 0,
        "OnlyGeneral": 0,
        "OnleyNTUST": 0,
        "OnlyMaster": 0,
        "OnlyUnderGraduate": 0,
        "OnlyNode": 0,
        "Language": LANGUAGE,
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def read_course(answer: object, code: str) -> Course | None:
    """The course ``code`` in the course query's parsed answer, or None when it lists none.

    The course query matches codes as prefixes and lists a course once per room and time; the last
    entry with the code wins, as v3's ``associateBy``. Only those entries are read: v3's Moshi
    failed the whole answer for one malformed course.

    Raises:
        AnswerError: The answer is not a list, or an entry of the course lacks its name, a whole
            number of members or a limit.
    """
    if not isinstance(answer, list):
        msg = "the answer is not a list of courses"
        raise AnswerError(msg)
    found: Course | None = None
    for entry in cast("list[object]", answer):
        fields = cast("dict[str, object]", entry) if isinstance(entry, dict) else {}
        if fields.get("CourseNo") == code:
            found = _course(code, fields)
    return found


def _course(code: str, fields: dict[str, object]) -> Course:
    name, chosen = fields.get("CourseName"), fields.get("ChooseStudent")
    if not isinstance(name, str):
        msg = f"{code}: CourseName is not text"
        raise AnswerError(msg)
    if not isinstance(chosen, int) or isinstance(chosen, bool):
        msg = f"{code}: ChooseStudent is not a whole number"
        raise AnswerError(msg)
    return Course(code, name, chosen, _limit(code, fields.get("Restrict2")))


def _limit(code: str, value: object) -> int:
    """``Restrict2`` as v3 read it: text, or a number as its JSON text (Moshi's ``nextString``).

    A limit that is not an Int (``""``, ``"abc"``, ``60.0``) is 0, as v3's ``?: 0``.
    """
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        msg = f"{code}: Restrict2 is neither text nor a number"
        raise AnswerError(msg)
    number = to_int_or_none(value if isinstance(value, str) else json.dumps(value))
    return 0 if number is None else number
