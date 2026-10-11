"""End times: v3's ``yyyy-MM-dd HH:mm`` read and shown in the configured zone.

v3 read them with Java's ``DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")`` and its SMART
resolver in the host's zone; the inventory lists the results verified with JDK 25.
"""

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from xincord.plugins.giveaway.times import format_end_time, parse_end_time

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import tzinfo

REASON = "End times are read and shown in the configured zone"
TAIPEI = ZoneInfo("Asia/Taipei")
NEW_YORK = ZoneInfo("America/New_York")


def epoch(*fields: int, zone: tzinfo = TAIPEI) -> int:
    """The epoch second of a wall time in ``zone``."""
    return int(datetime(*fields, tzinfo=zone).timestamp())


@pytest.fixture
def host_zone(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The process's local time zone is Asia/Taipei for the test."""
    monkeypatch.setenv("TZ", "Asia/Taipei")
    time.tzset()
    yield
    monkeypatch.undo()  # the process's own zone again
    time.tzset()


@pytest.mark.parametrize(
    ("text", "zone", "expected"),
    [
        ("2026-03-01 10:00", TAIPEI, 1772330400),
        ("9999-12-31 23:59", UTC, 253402300740),
        ("0001-01-01 00:00", UTC, -62135596800),
        ("2026-01-05 00:00", NEW_YORK, epoch(2026, 1, 5, zone=NEW_YORK)),
    ],
)
def test_accepted(text: str, zone: tzinfo, expected: int) -> None:
    """Requirement: End times are read and shown in the configured zone."""
    assert parse_end_time(text, zone) == expected


@pytest.mark.parametrize(
    ("text", "fields"),
    [
        ("2026-02-30 10:00", (2026, 2, 28, 10)),
        ("2025-02-29 10:00", (2025, 2, 28, 10)),
        ("2024-02-30 10:00", (2024, 2, 29, 10)),
        ("2026-04-31 10:00", (2026, 4, 30, 10)),
    ],
)
def test_clamped_day(text: str, fields: tuple[int, ...]) -> None:
    """Requirement: End times are read and shown in the configured zone."""
    assert parse_end_time(text, TAIPEI) == epoch(*fields)


@pytest.mark.parametrize(
    ("text", "fields"),
    [
        ("2026-12-31 24:00", (2027, 1, 1)),
        ("2026-02-30 24:00", (2026, 3, 1)),
        ("2026-03-01 24:00", (2026, 3, 2)),
    ],
)
def test_end_of_day(text: str, fields: tuple[int, ...]) -> None:
    """Requirement: End times are read and shown in the configured zone."""
    assert parse_end_time(text, TAIPEI) == epoch(*fields)


@pytest.mark.parametrize(
    "text",
    [
        "2026-01-05 24:01",
        "2026-01-05 23:60",
        "2026-1-05 10:00",
        "2026-01-5 10:00",
        "2026-01-05 9:00",
        "2026-01-05 10:0",
        "2026-01-05T10:00",
        "2026-01-05 10:00:00",
        "2026/01/05 10:00",
        "26-01-05 10:00",
        "0000-01-05 10:00",
        "2026-01-05  10:00",
        "+2026-01-05 10:00",
        "".join(chr(0xFF10 + int(char)) if char.isdigit() else char for char in "2026-01-05 10:00"),
        "2026-00-05 10:00",
        "2026-13-05 10:00",
        "2026-01-00 10:00",
        "2026-01-32 10:00",
        "+12026-01-05 10:00",
        "9999-12-31 24:00",
        " 2026-01-05 10:00",
        "",
    ],
)
def test_rejected(text: str) -> None:
    """Requirement: End times are read and shown in the configured zone."""
    assert parse_end_time(text, TAIPEI) is None


def test_zone_transitions() -> None:
    """Requirement: End times are read and shown in the configured zone."""
    # Java's atZone moves a time in a gap forward and takes the earlier offset in an overlap.
    assert parse_end_time("2026-03-08 02:30", NEW_YORK) == epoch(2026, 3, 8, 7, 30, zone=UTC)
    assert parse_end_time("2026-11-01 01:30", NEW_YORK) == epoch(2026, 11, 1, 5, 30, zone=UTC)


@pytest.mark.parametrize(
    ("moment", "zone", "shown"),
    [
        (1772330400, TAIPEI, "2026-03-01 10:00"),
        (1772330400, UTC, "2026-03-01 02:00"),
        (epoch(999, 1, 2, 3, 4, zone=UTC), UTC, "0999-01-02 03:04"),
    ],
)
def test_shown(moment: int, zone: tzinfo, shown: str) -> None:
    """Requirement: End times are read and shown in the configured zone."""
    assert format_end_time(moment, zone) == shown
    assert parse_end_time(shown, zone) == moment


@pytest.mark.usefixtures("host_zone")
def test_host_zone() -> None:
    """Requirement: End times are read and shown in the configured zone."""
    assert parse_end_time("2026-03-01 10:00", None) == 1772330400
    assert format_end_time(1772330400, None) == "2026-03-01 10:00"


def test_beyond_9999_in_utc() -> None:
    """Requirement: End times are read and shown in the configured zone."""
    # 9999-12-31 23:59 in New York is in the year 10000 in UTC, which datetime cannot show.
    assert parse_end_time("9999-12-31 23:59", NEW_YORK) is None
    late = parse_end_time("9999-12-31 18:59", NEW_YORK)
    assert late is not None
    assert format_end_time(late, NEW_YORK) == "9999-12-31 18:59"
