"""Voice channel status changes and the audit log entries that name their member.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:117-141
"""

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

SET = 192  # the audit log type of a set or changed status (JDA's VOICE_CHANNEL_STATUS_UPDATE)
CLEARED = 193  # the audit log type of a cleared status (VOICE_CHANNEL_STATUS_DELETE)
WINDOW = timedelta(seconds=30)  # how far from the event an entry may be, Discord's clock or ours
RETRY_DELAY = 2.0  # seconds before the audit log is read again for an entry that came late

type Fetch = Callable[[int], Awaitable[object | None]]  # reads the audit log of one type
type Sleep = Callable[[float], Awaitable[None]]


def match(log: object, kind: int, channel_id: int, status: str, at: datetime) -> int | None:
    """The user of the audit log entry of a status change, from an audit log response.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError


async def find_actor(
    fetch: Fetch, channel_id: int, status: str, at: datetime, sleep: Sleep
) -> int | None:
    """The user who set ``status`` on channel ``channel_id`` at ``at``, from the audit log.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError
