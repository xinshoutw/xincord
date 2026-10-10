"""The audit log entry that names the member of a voice channel status change.

v3 took the user of the guild's newest type-192 entry, whatever its channel or age.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:117-141
"""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from discord.utils import time_snowflake

from xincord.plugins.voice_logger.status import CLEARED, SET, find_actor, match

AT = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)  # when the status update arrived


def entry(
    user_id: int,
    channel_id: int,
    *,
    kind: int = SET,
    status: str | None = None,
    ago: timedelta = timedelta(seconds=1),
) -> dict[str, object]:
    """An audit log entry of ``user_id`` for ``channel_id``, made ``ago`` before ``AT``.

    The channel is in ``options.channel_id``, as Discord documents it.
    """
    options: dict[str, object] = {"channel_id": str(channel_id)}
    if status is not None:
        options["status"] = status
    return {
        "id": str(time_snowflake(AT - ago)),
        "action_type": kind,
        "user_id": str(user_id),
        "target_id": None,
        "options": options,
    }


def targeted(found: dict[str, object]) -> dict[str, object]:
    """``found`` with its channel in ``target_id`` instead, as JDA read type 192's target."""
    options = dict(cast("dict[str, object]", found["options"]))
    return found | {"target_id": options.pop("channel_id"), "options": options}


def log(*entries: dict[str, object]) -> dict[str, object]:
    """An audit log response with ``entries``, newest first, as Discord sends them."""
    return {"audit_log_entries": list(entries), "users": []}


def test_matching_entry() -> None:
    """Requirement: Status changes name their member from the audit log."""
    newer = entry(8, 31, ago=timedelta(seconds=1))  # another channel's status
    older = entry(7, 30, ago=timedelta(seconds=2))

    assert match(log(newer, older), SET, 30, "Gaming", AT) == 7
    assert match(log(targeted(entry(7, 30))), SET, 30, "Gaming", AT) == 7


def test_same_status_first() -> None:
    """Requirement: Status changes name their member from the audit log."""
    other = entry(8, 30, status="Chill", ago=timedelta(seconds=1))
    same = entry(7, 30, status="Gaming", ago=timedelta(seconds=3))
    unknown = entry(9, 30, ago=timedelta(seconds=1))

    assert match(log(other, same), SET, 30, "Gaming", AT) == 7
    assert match(log(unknown, other), SET, 30, "Gaming", AT) == 9  # else the newest one


@pytest.mark.xfail(strict=True, reason="Status changes name their member from the audit log")
def test_earlier_status_entry() -> None:
    """Requirement: Status changes name their member from the audit log."""
    # Member 8 set Gaming 10 seconds ago; the entry of the change to Chill is not there yet.
    earlier = entry(8, 30, status="Gaming", ago=timedelta(seconds=10))

    assert match(log(earlier), SET, 30, "Chill", AT) is None
    # A cleared status takes its entry whatever status the entry may name.
    assert match(log(entry(7, 30, kind=CLEARED, status="Chill")), CLEARED, 30, "", AT) == 7


@pytest.mark.parametrize(
    "found",
    [
        entry(7, 30, ago=timedelta(minutes=10)),  # an earlier change
        entry(7, 30, ago=-timedelta(minutes=10)),  # far ahead of the event
        entry(7, 30, kind=CLEARED),  # another type
        {"id": "x", "action_type": SET, "user_id": "7", "options": {"channel_id": "30"}},
        {"id": str(time_snowflake(AT)), "action_type": SET, "options": {"channel_id": "30"}},
        "not an entry",
    ],
)
def test_no_entry(found: object) -> None:
    """Requirement: Status changes name their member from the audit log."""
    assert match({"audit_log_entries": [found]}, SET, 30, "Gaming", AT) is None


@pytest.mark.parametrize("response", [None, [], {}, {"audit_log_entries": "none"}])
def test_unreadable_response(response: object) -> None:
    """Requirement: Status changes name their member from the audit log."""
    assert match(response, SET, 30, "Gaming", AT) is None


class AuditLog:
    """Answers each read of the audit log with the next response, and records the reads."""

    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.kinds: list[int] = []
        self.sleeps: list[float] = []

    async def fetch(self, kind: int) -> object | None:
        """Read the audit log of type ``kind``."""
        self.kinds.append(kind)
        return self.responses.pop(0)

    async def sleep(self, seconds: float) -> None:
        """Wait ``seconds``, at once."""
        self.sleeps.append(seconds)


async def test_first_read() -> None:
    """Requirement: Status changes name their member from the audit log."""
    audit = AuditLog(log(entry(7, 30)))

    assert await find_actor(audit.fetch, 30, "Gaming", AT, audit.sleep) == 7
    assert (audit.kinds, audit.sleeps) == ([SET], [])


async def test_late_entry() -> None:
    """Requirement: Status changes name their member from the audit log."""
    audit = AuditLog(log(), log(entry(7, 30, kind=CLEARED)))

    assert await find_actor(audit.fetch, 30, "", AT, audit.sleep) == 7
    assert (audit.kinds, audit.sleeps) == ([CLEARED, CLEARED], [2.0])  # a cleared status: 193


@pytest.mark.xfail(strict=True, reason="Status changes name their member from the audit log")
async def test_earlier_change_entry() -> None:
    """Requirement: Status changes name their member from the audit log."""
    gaming = entry(8, 30, status="Gaming", ago=timedelta(seconds=10))
    audit = AuditLog(log(gaming), log(entry(9, 30, status="Chill"), gaming))

    assert await find_actor(audit.fetch, 30, "Chill", AT, audit.sleep) == 9
    assert (audit.kinds, audit.sleeps) == ([SET, SET], [2.0])


async def test_no_entry_after_two_reads() -> None:
    """Requirement: Status changes name their member from the audit log."""
    audit = AuditLog(log(), log(entry(7, 31)))

    assert await find_actor(audit.fetch, 30, "Gaming", AT, audit.sleep) is None
    assert (audit.kinds, audit.sleeps) == ([SET, SET], [2.0])


async def test_unreadable_audit_log() -> None:
    """Requirement: Status changes name their member from the audit log."""
    audit = AuditLog(None)  # Discord refused it; the reader logged why

    assert await find_actor(audit.fetch, 30, "Gaming", AT, audit.sleep) is None
    assert (audit.kinds, audit.sleeps) == ([SET], [])
