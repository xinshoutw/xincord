"""Voice channel status changes and the audit log entries that name their member.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:117-141
"""

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, cast

from discord.utils import snowflake_time

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

SET = 192  # the audit log type of a set or changed status (JDA's VOICE_CHANNEL_STATUS_UPDATE)
CLEARED = 193  # the audit log type of a cleared status (VOICE_CHANNEL_STATUS_DELETE)
WINDOW = timedelta(seconds=30)  # how far from the event an entry may be, Discord's clock or ours
RETRY_DELAY = 2.0  # seconds before the audit log is read again for an entry that came late
ATTEMPTS = 2  # reads of the audit log per status change
DIGITS = re.compile(r"[0-9]+")

type Fetch = Callable[[int], Awaitable[object | None]]  # reads the audit log of one type
type Sleep = Callable[[float], Awaitable[None]]


def match(log: object, kind: int, channel_id: int, status: str, at: datetime) -> int | None:
    """The user of the audit log entry of a status change, from an audit log response.

    The entry must be of type ``kind`` (192 for a set status, 193 for a cleared one), name the
    channel in ``options.channel_id`` (Discord's documentation) or ``target_id`` (JDA's target),
    and be made within 30 seconds of ``at``. Of those, the newest one with the new status wins
    (Discord puts it in ``options.status`` for type 192), else the newest one. v3 took the
    guild's newest type-192 entry, whatever its channel or age.
    """
    response = cast("dict[str, object]", log) if isinstance(log, dict) else {}
    entries = response.get("audit_log_entries")
    found = [
        entry
        for entry in map(_entry, cast("list[object]", entries) if isinstance(entries, list) else [])
        if entry is not None
        and entry.kind == kind
        and entry.channel_id == channel_id
        and abs(entry.created - at) <= WINDOW
    ]
    same = [entry for entry in found if entry.status == status]
    return (same or found)[0].user_id if found else None


async def find_actor(
    fetch: Fetch, channel_id: int, status: str, at: datetime, sleep: Sleep
) -> int | None:
    """The user who set ``status`` on channel ``channel_id`` at ``at``, from the audit log.

    ``fetch`` reads the audit log of one type, and returns None when Discord refused it (and
    logs why). An entry that is not there yet is looked for once more after 2 seconds, in case
    Discord wrote it after the gateway event.
    """
    kind = SET if status else CLEARED
    for attempt in range(ATTEMPTS):
        if attempt:
            await sleep(RETRY_DELAY)
        log = await fetch(kind)
        if log is None:
            return None
        if (user := match(log, kind, channel_id, status, at)) is not None:
            return user
    return None


@dataclass(frozen=True)
class _Entry:
    """The fields of an audit log entry that a status change is matched with."""

    kind: object
    channel_id: int | None
    user_id: int
    created: datetime
    status: object


def _entry(raw: object) -> _Entry | None:
    """The fields of one entry of Discord's response, or None for one without a user."""
    if not isinstance(raw, dict):
        return None
    fields = cast("dict[str, object]", raw)
    entry_id, user_id = _snowflake(fields.get("id")), _snowflake(fields.get("user_id"))
    if entry_id is None or user_id is None:
        return None
    options = fields.get("options")
    extra = cast("dict[str, object]", options) if isinstance(options, dict) else {}
    channel = _snowflake(extra.get("channel_id")) or _snowflake(fields.get("target_id"))
    created = snowflake_time(entry_id)
    return _Entry(fields.get("action_type"), channel, user_id, created, extra.get("status"))


def _snowflake(value: object) -> int | None:
    """An ID that Discord sent as a decimal string, or None."""
    return int(value) if isinstance(value, str) and DIGITS.fullmatch(value) else None
