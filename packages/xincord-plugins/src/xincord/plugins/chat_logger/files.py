"""The message files' names and the ranges of message IDs that they hold.

``data/ChatLogger/messages-<start>.db`` holds the messages created from ``<start>``, a UTC second,
up to the next file's start; the oldest file also holds the older ones. v3 kept one file per guild
with one table per channel instead.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:164-187
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime


def file_name(start: datetime) -> str:
    """The name of the file whose messages start at ``start``, a whole UTC second."""
    raise NotImplementedError


def parse_name(name: str) -> datetime | None:
    """The start of the message file called ``name``, or None for any other file."""
    raise NotImplementedError


def first_id(start: datetime) -> int:
    """The lowest message ID that Discord can give a message created at ``start``."""
    raise NotImplementedError


def first_second(message_id: int) -> datetime:
    """The UTC second in which a message was created, as its ID tells: a first file's start."""
    raise NotImplementedError


def route(first_ids: Sequence[int], message_id: int) -> int:
    """The index of the file that holds ``message_id``, given each file's first ID in order."""
    raise NotImplementedError


def next_start(last_id: int, newest: datetime) -> datetime:
    """The start of the file after the newest one, which starts at ``newest``.

    ``last_id`` is the newest file's highest stored message ID.
    """
    raise NotImplementedError
