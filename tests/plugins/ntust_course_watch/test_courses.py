"""The course query's request body and answer, and v3's seats."""

import json
from typing import Any

import pytest

from plugin_fakes import FIXTURES, golden
from xincord.plugins.ntust_course_watch.courses import (
    AnswerError,
    Course,
    read_course,
    request_text,
    to_int_or_none,
)

GOLDEN = golden("ntust_course_watch")
ANSWER_TEXT = (FIXTURES / "plugins" / "ntust_course_watch" / "answer.json").read_text("utf-8")


def answer() -> list[dict[str, Any]]:
    """A fresh copy of NTUST's answer for the prefix CE162A."""
    entries: list[dict[str, Any]] = json.loads(ANSWER_TEXT)
    return entries


def with_entry(code: str, **fields: object) -> list[dict[str, Any]]:
    """The answer with the last entry of ``code`` changed."""
    entries = answer()
    last = max(index for index, entry in enumerate(entries) if entry["CourseNo"] == code)
    entries[last] = {**entries[last], **fields}
    return entries


def test_request_body() -> None:
    """Requirement: Course seats come from NTUST's course query."""
    # The course query site's body (2026-10-11): one code, OnleyNTUST as the API spells it; v3
    # sent CourseTeacher " " and no code, which NTUST's server no longer answers.
    assert request_text("1151", "CE162A001") == GOLDEN["request"]


@pytest.mark.parametrize("code", ["CE162A001", "CE162A011", "CE162A012"])
def test_answer(code: str) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    expected = GOLDEN["courses"][code]

    course = read_course(answer(), code)

    assert course == Course(code, expected["name"], expected["chosen"], expected["limit"])
    assert course is not None
    assert course.full is expected["full"]


def test_last_entry_wins() -> None:
    """Requirement: Course seats come from NTUST's course query."""
    # The course query lists a course once per room and time; v3's associateBy kept the last.
    course = read_course(with_entry("CE162A001", ChooseStudent=60), "CE162A001")

    assert course is not None
    assert course.chosen == 60
    assert course.full


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        pytest.param("60", 60, id="text"),
        pytest.param("0", 0, id="zero"),
        pytest.param("", 0, id="empty"),
        pytest.param("abc", 0, id="not a number"),
        pytest.param(" 60", 0, id="space"),
        pytest.param("+60", 60, id="plus"),
        pytest.param("2147483647", 2147483647, id="Int.MAX_VALUE"),
        pytest.param("99999999999", 0, id="beyond an Int"),
        pytest.param(60, 60, id="number"),
        pytest.param(60.0, 0, id="decimal number"),
    ],
)
def test_limits(limit: object, expected: int) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    course = read_course(with_entry("CE162A001", Restrict2=limit), "CE162A001")

    assert course is not None
    assert course.limit == expected
    assert course.full is (course.chosen >= expected)  # 25 chosen: full only below 26


@pytest.mark.parametrize(
    ("text", "number"),
    [
        pytest.param("42", 42, id="digits"),
        pytest.param("-42", -42, id="minus"),
        pytest.param("-2147483648", -2147483648, id="Int.MIN_VALUE"),
        pytest.param("2147483648", None, id="beyond Int.MAX_VALUE"),
        pytest.param("-", None, id="sign only"),
        pytest.param("4_2", None, id="underscore"),
        pytest.param("42 ", None, id="trailing space"),
        pytest.param(chr(0xFF14) + chr(0xFF12), 42, id="full-width digits"),
        pytest.param("0" * 4400 + "1", None, id="beyond Python's conversion limit"),
    ],
)
def test_to_int_or_none(text: str, number: int | None) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    assert to_int_or_none(text) == number


def test_digits_outside_the_bmp() -> None:
    """Requirement: Course seats come from NTUST's course query."""
    sixty = chr(0x1D7D4) + chr(0x1D7CE)  # MATHEMATICAL BOLD DIGIT SIX and ZERO

    # Kotlin's String is UTF-16: each of these digits was two surrogates, which are no digits.
    assert to_int_or_none(sixty) is None
    course = read_course(with_entry("CE162A001", Restrict2=sixty), "CE162A001")
    assert course is not None
    assert course.limit == 0
    assert course.full


@pytest.mark.parametrize(
    "entries",
    [
        pytest.param(answer(), id="other courses"),
        pytest.param([], id="empty"),
        pytest.param([{"CourseNo": 7}, "junk", {"ChooseStudent": 1}], id="other entries broken"),
    ],
)
def test_course_missing(entries: list[object]) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    assert read_course(entries, "CE162A099") is None


def test_other_entries_are_not_read() -> None:
    """Requirement: Course seats come from NTUST's course query."""
    # v3's Moshi failed the whole answer for one malformed course; only the checked one is read.
    entries: list[object] = [*with_entry("CE162A002", ChooseStudent=None), "junk", None]

    course = read_course(entries, "CE162A001")

    assert course is not None
    assert course.chosen == 25


@pytest.mark.parametrize(
    ("value", "message"),
    [
        pytest.param({"Message": "error"}, "not a list", id="object"),
        pytest.param(None, "not a list", id="null"),
        pytest.param(with_entry("CE162A001", ChooseStudent=None), "ChooseStudent", id="no count"),
        pytest.param(
            with_entry("CE162A001", ChooseStudent="25"), "ChooseStudent", id="count as text"
        ),
        pytest.param(
            with_entry("CE162A001", ChooseStudent=True), "ChooseStudent", id="count as boolean"
        ),
        pytest.param(with_entry("CE162A001", Restrict2=None), "Restrict2", id="no limit"),
        pytest.param(with_entry("CE162A001", Restrict2=False), "Restrict2", id="limit boolean"),
        pytest.param(with_entry("CE162A001", CourseName=None), "CourseName", id="no name"),
    ],
)
def test_refused_answers(value: object, message: str) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    with pytest.raises(AnswerError, match=message):
        read_course(value, "CE162A001")
