"""The message files' names and the ranges of message IDs that they hold.

``data/ChatLogger/messages-<start>.db`` holds the messages created from ``<start>``, a UTC second,
up to the next file's start; the oldest file also holds the older ones. v3 kept one file per guild
with one table per channel instead.
"""

import re
from bisect import bisect_right
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from discord.utils import snowflake_time, time_snowflake

if TYPE_CHECKING:
    from collections.abc import Sequence

# ISO 8601's basic format in UTC: sorted by name, readable, and free of the colons that some file
# systems refuse.
STAMP = "%Y%m%dT%H%M%SZ"
NAME = re.compile(r"messages-(\d{8}T\d{6}Z)\.db")
SECOND = timedelta(seconds=1)


def file_name(start: datetime) -> str:
    """The name of the file whose messages start at ``start``, a whole UTC second."""
    return f"messages-{start.astimezone(UTC).strftime(STAMP)}.db"


def parse_name(name: str) -> datetime | None:
    """The start of the message file called ``name``, or None for any other file."""
    if (match := NAME.fullmatch(name)) is None:
        return None
    try:
        return datetime.strptime(match[1], STAMP).replace(tzinfo=UTC)
    except ValueError:  # a date that does not exist, such as a 13th month
        return None


def first_id(start: datetime) -> int:
    """The lowest message ID that Discord can give a message created at ``start``."""
    return time_snowflake(start)


def first_second(message_id: int) -> datetime:
    """The UTC second in which a message was created, as its ID tells: a first file's start."""
    return snowflake_time(message_id).replace(microsecond=0)


def route(first_ids: Sequence[int], message_id: int) -> int:
    """The index of the file that holds ``message_id``, given each file's first ID in order.

    A message older than every file belongs to the oldest one: a message created a moment before
    the first stored one, or one stored before the older files expired.
    """
    return max(bisect_right(first_ids, message_id) - 1, 0)


def next_start(last_id: int, newest: datetime) -> datetime:
    """The start of the file after the newest one, which starts at ``newest``.

    ``last_id`` is the newest file's highest stored message ID: the new file starts at the second
    after that message's, so that every stored message stays in the file that holds it, and after
    the newest file's own start, so that the names keep their order.
    """
    return max(first_second(last_id) + SECOND, newest + SECOND)


def expired(first_ids: Sequence[int], before: int) -> int:
    """How many of the oldest files hold only messages below ``before``, never the newest.

    A file's messages lie below the next file's first ID, so the file expired once that ID is at
    or below ``before``.
    """
    return bisect_right(first_ids, before, lo=1) - 1
