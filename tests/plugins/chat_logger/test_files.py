"""The message files' names and the ranges of message IDs that they hold.

v3 kept one file per guild, ``plugins/ChatLogger/data/<guildId>.db``, with one table per channel;
there is no Kotlin counterpart to the ranges.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:164-187
"""

from datetime import UTC, datetime, timedelta

import pytest
from discord.utils import time_snowflake

from xincord.plugins.chat_logger.files import (
    expired,
    file_name,
    first_id,
    first_second,
    next_start,
    parse_name,
    route,
)

NOON = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)


def at(seconds: float) -> int:
    """The lowest ID of a message created ``seconds`` after ``NOON``."""
    return time_snowflake(NOON + timedelta(seconds=seconds))


def test_names() -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    start = NOON + timedelta(seconds=5)

    assert file_name(start) == "messages-20261011T120005Z.db"
    assert parse_name("messages-20261011T120005Z.db") == start
    assert parse_name(file_name(start)) == start


@pytest.mark.parametrize(
    "name",
    [
        "messages-20261011T120005Z.db-journal",  # SQLite's journal beside a file
        "messages-20261011T120005Z.db.tmp",  # a new file being created
        "messages-20261340T120005Z.db",  # no 13th month
        "messages-2026-10-11.db",
        "notes.txt",
    ],
)
def test_other_names(name: str) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    assert parse_name(name) is None


def test_first_id_and_second() -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    created = at(5.25) + 12345  # worker, process and increment bits after the time

    assert first_id(NOON) == time_snowflake(NOON)
    assert first_id(NOON) < at(0.001)
    # The first file is named after the second in which its first message was created.
    assert first_second(created) == NOON + timedelta(seconds=5)


def test_route() -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    first_ids = [at(0), at(60), at(120)]

    assert route(first_ids, at(-30)) == 0  # older than every file: the oldest holds it
    assert route(first_ids, at(0)) == 0
    assert route(first_ids, at(60) - 1) == 0
    assert route(first_ids, at(60)) == 1
    assert route(first_ids, at(119.999)) == 1
    assert route(first_ids, at(120)) == 2
    assert route(first_ids, at(86400)) == 2
    assert route([at(0)], at(-1)) == 0


def test_next_start() -> None:
    """Requirement: A new message file starts when the newest is full."""
    newest = NOON

    # The second after the newest stored message's: every stored ID stays below the new file.
    assert next_start(at(5.25) + 99, newest) == NOON + timedelta(seconds=6)
    assert first_id(next_start(at(5.999) + (1 << 22) - 1, newest)) > at(5.999) + (1 << 22) - 1
    # A first file whose rows are all older than its own start still gets a later successor.
    assert next_start(at(-10), newest) == NOON + timedelta(seconds=1)


def test_expired() -> None:
    """Requirement: Stored messages are kept for the retention period."""
    first_ids = [at(0), at(60), at(120)]

    assert expired(first_ids, at(59)) == 0  # the first file may hold a message from 00:59
    assert expired(first_ids, at(60)) == 1  # its messages are all older than its successor
    assert expired(first_ids, at(119)) == 1
    assert expired(first_ids, at(120)) == 2
    assert expired(first_ids, at(86400)) == 2  # never the newest file
    assert expired([at(0)], at(86400)) == 0
    assert expired([], at(86400)) == 0
