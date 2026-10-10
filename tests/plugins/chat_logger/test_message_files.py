"""The stored messages in the plugin's own files: their ranges, new files and closing.

v3 kept one file per guild with one table per channel, through SQLiteAPI's connections, which it
never closed; the files of time ranges and their thread are new.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:16-188
    XsDiscordBotKt@3a59607:Plugins/API/SQLiteAPI/src/main/kotlin/api/sqlite/SQLiteFileManager.kt:8-46
"""

import asyncio
import gc
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from discord.utils import time_snowflake

from xincord.plugins.chat_logger import messages
from xincord.plugins.chat_logger.files import file_name
from xincord.plugins.chat_logger.messages import Edit, MessageFiles, Stored

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Sequence
    from pathlib import Path

type Row = tuple[int, int, int, int, str, int]  # v3's columns, with the guild and the channel

NOON = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)
MIB = 1024 * 1024
LONG = "x" * 4000  # about a page of a file
FIRST = "messages-20261011T120005Z.db"  # the file of a first message created at 12:00:05


def at(seconds: float, sequence: int = 0) -> int:
    """The ID of a message created ``seconds`` after noon; ``sequence`` sets its lowest bits."""
    return time_snowflake(NOON + timedelta(seconds=seconds)) + sequence


def name(seconds: int) -> str:
    """The name of the file that starts ``seconds`` after noon."""
    return file_name(NOON + timedelta(seconds=seconds))


def rows(directory: Path) -> dict[str, list[Row]]:
    """Each message file's rows by the file's name, read through a connection of the test's own."""
    found: dict[str, list[Row]] = {}
    for path in sorted(directory.glob("messages-*.db")):
        with closing(sqlite3.connect(path)) as db:
            found[path.name] = [
                tuple(row)
                for row in db.execute(
                    "SELECT message_id, guild_id, channel_id, user_id, message, update_count"
                    " FROM messages ORDER BY message_id"
                )
            ]
    return found


def ids(directory: Path) -> dict[str, list[int]]:
    """Each message file's message IDs by the file's name."""
    return {file: [row[0] for row in found] for file, found in rows(directory).items()}


class Opener:
    """Opens message files in ``directory`` and remembers them, to close them after the test."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.opened: list[MessageFiles] = []

    async def __call__(self, max_bytes: int = MIB) -> MessageFiles:
        """Open the files with a size limit in bytes."""
        files = MessageFiles(self.directory, max_bytes)
        self.opened.append(files)
        await files.open()
        return files


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    """The plugin's data directory, which nothing created yet."""
    return tmp_path / "data" / "ChatLogger"


@pytest.fixture
async def open_files(directory: Path) -> AsyncGenerator[Opener]:
    """Open message files; each is closed after the test, or its connections would leak."""
    opener = Opener(directory)
    yield opener
    for files in opener.opened:
        await files.close()


async def test_no_message_no_file(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    files = await open_files()

    assert files.is_open
    assert await files.edit(at(5), "hi") is None
    assert await files.pop_all([at(5)]) == []
    assert await files.guild_ids() == []
    assert not directory.exists()  # nothing is created before the first message


async def test_first_file(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    files = await open_files()
    message = at(5.25, 7)  # created at 12:00:05.250

    await files.add(message, 10, 30, 7, "hello")

    assert rows(directory) == {FIRST: [(message, 10, 30, 7, "hello", 0)]}


async def test_messages_of_older_files(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    files = await open_files(1)  # each message fills the newest file: a new one starts after it
    first, second, third = at(5), at(10), at(20)
    for message_id, text in ((first, "a"), (second, "b"), (third, "c")):
        await files.add(message_id, 10, 30, 7, text)

    assert ids(directory) == {FIRST: [first], name(6): [second], name(11): [third], name(21): []}
    assert await files.edit(first, "a2") == Edit(before="a", user_id=7, count=1)
    assert await files.edit(third, "c2") == Edit(before="c", user_id=7, count=1)
    assert await files.pop(second) == Stored(text="b", user_id=7, count=0)
    assert rows(directory) == {
        FIRST: [(first, 10, 30, 7, "a2", 1)],
        name(6): [],
        name(11): [(third, 10, 30, 7, "c2", 1)],
        name(21): [],
    }
    assert await files.pop_all([third, at(30), first]) == [  # oldest first
        (first, Stored("a2", 7, 1)),
        (third, Stored("c2", 7, 1)),
    ]
    assert ids(directory) == {FIRST: [], name(6): [], name(11): [], name(21): []}


async def test_late_message(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    files = await open_files(1)
    on_time = at(10)
    await files.add(on_time, 10, 30, 7, "on time")  # the first file, then one from 12:00:11
    late, older = at(10.5), at(2)

    await files.add(late, 10, 30, 7, "late")  # created before 12:00:11
    await files.add(older, 10, 30, 7, "older")  # older than every file: the oldest holds it

    # Only messages stored in the newest file start a new one.
    assert ids(directory) == {name(10): [older, on_time, late], name(11): []}
    assert await files.edit(late, "edited") == Edit(before="late", user_id=7, count=1)
    assert await files.edit(older, "edited") == Edit(before="older", user_id=7, count=1)


async def test_files_kept_across_loads(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    files = await open_files(1)
    await files.add(at(5), 10, 30, 7, "a")
    await files.add(at(10), 10, 30, 7, "b")
    await files.close()
    names = list(rows(directory))

    again = await open_files(1)

    assert await again.edit(at(5), "a2") == Edit(before="a", user_id=7, count=1)
    assert await again.pop(at(10)) == Stored(text="b", user_id=7, count=0)
    assert list(rows(directory)) == names  # no file started


async def test_other_files(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    directory.mkdir(parents=True)
    (directory / "notes.txt").write_text("kept", encoding="utf-8")
    (directory / "messages-2026.db").write_bytes(b"not a message file")
    files = await open_files()

    await files.add(at(5), 10, 30, 7, "a")

    assert sorted(path.name for path in directory.iterdir()) == [
        "messages-2026.db",
        FIRST,
        "notes.txt",
    ]
    assert (directory / "messages-2026.db").read_bytes() == b"not a message file"


async def test_add(open_files: Opener, directory: Path) -> None:
    """Requirement: Guild messages are stored."""
    files = await open_files()

    await files.add(at(5), 10, 30, 7, "hello")
    await files.add(at(5), 10, 30, 7, "again")  # a replayed event keeps the first row
    await files.add(at(6), 10, 41, 8, "")

    assert rows(directory) == {FIRST: [(at(5), 10, 30, 7, "hello", 0), (at(6), 10, 41, 8, "", 0)]}


async def test_edit(open_files: Opener, directory: Path) -> None:
    """Requirement: Edits of stored messages are logged."""
    files = await open_files()
    await files.add(at(5), 10, 30, 7, "hello")

    assert await files.edit(at(5), "hi") == Edit(before="hello", user_id=7, count=1)
    assert await files.edit(at(5), "hey") == Edit(before="hi", user_id=7, count=2)
    assert await files.edit(at(5), "hey") is None  # the same text: nothing changes
    assert await files.edit(at(6), "hi") is None  # not stored: not stored on an edit either
    assert rows(directory) == {FIRST: [(at(5), 10, 30, 7, "hey", 2)]}


async def test_pop(open_files: Opener, directory: Path) -> None:
    """Requirement: Deletions of stored messages are logged."""
    files = await open_files()
    await files.add(at(5), 10, 30, 7, "hello")
    await files.edit(at(5), "hi")

    assert await files.pop(at(5)) == Stored(text="hi", user_id=7, count=1)
    assert await files.pop(at(5)) is None  # v3 kept the text of deleted messages
    assert rows(directory) == {FIRST: []}


async def test_forget(open_files: Opener, directory: Path) -> None:
    """Requirement: Data is forgotten with the guild."""
    files = await open_files(1)  # a file for each message
    await files.add(at(5), 20, 30, 7, "a")
    await files.add(at(10), 10, 31, 7, "b")
    await files.add(at(20), 20, 32, 7, "c")

    assert await files.guild_ids() == [10, 20]
    assert await files.forget(20) == 2
    assert await files.guild_ids() == [10]
    assert await files.forget(20) == 0
    assert ids(directory) == {FIRST: [], name(6): [at(10)], name(11): [], name(21): []}


async def test_prune(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages are kept for the retention period."""

    def ago(days: float) -> int:
        return time_snowflake(NOON - timedelta(days=days))

    files = await open_files()
    kept = [ago(29), ago(1)]
    old = [ago(40), ago(35), ago(31), ago(30.5), ago(30.1)]
    for message_id in (*kept, *old):
        await files.add(message_id, 10, 30, 7, "text")

    # Two at a time, so that one deletion never holds the files' thread long.
    assert await files.prune(ago(30), batch=2) == 5
    assert [message_id for found in ids(directory).values() for message_id in found] == kept
    assert await files.prune(ago(30), batch=2) == 0


async def test_failed_work_keeps_nothing(open_files: Opener, directory: Path) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    files = await open_files()
    await files.add(at(5), 10, 30, 7, "a")
    [path] = directory.glob("messages-*.db")

    def broken(db: sqlite3.Connection) -> None:
        db.execute("DELETE FROM messages")
        db.execute("SELECT * FROM missing")

    # Each job's work in a file is one transaction: a failure keeps none of it.
    with closing(messages.connect(path)) as db, pytest.raises(sqlite3.OperationalError):
        messages.transaction(db, broken)

    assert rows(directory) == {FIRST: [(at(5), 10, 30, 7, "a", 0)]}


async def test_expired_files(
    open_files: Opener,
    directory: Path,
    write_file: Callable[[datetime, Sequence[int]], str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Stored messages are kept for the retention period."""

    def ago(days: float) -> datetime:
        return NOON - timedelta(days=days)

    def created(*days: float) -> list[int]:
        return [time_snowflake(ago(day)) for day in days]

    # The first file's range ends 1830 days ago, the second's 1800 days ago, the third's never.
    first = write_file(ago(1900), created(1900, 1840))
    second = write_file(ago(1830), created(1828, 1810))
    third = write_file(ago(1800), created(1))
    files = await open_files()

    with caplog.at_level(logging.INFO):
        deleted = await files.prune(time_snowflake(ago(1826)))

    assert deleted == 1  # 1828 days old; the first file's messages left with the file
    assert ids(directory) == {second: created(1810), third: created(1)}
    assert f"ChatLogger deleted the message file {first}, whose messages all expired" in caplog.text
    await files.prune(time_snowflake(NOON))  # every message expired: the newest file stays
    assert ids(directory) == {third: []}


async def test_full_file(open_files: Opener, directory: Path) -> None:
    """Requirement: A new message file starts when the newest is full."""
    limit = 64 * 1024
    files = await open_files(limit)
    stored: list[int] = []
    for second in range(40):  # 160 KiB at most
        stored.append(at(second, 3))
        await files.add(stored[-1], 10, 30, 7, LONG)
        if len(list(directory.glob("messages-*.db"))) > 1:
            break
    last = len(stored) - 1  # the second of the message that filled the file

    full, new = list(rows(directory))
    assert (full, new) == (name(0), name(last + 1))
    assert (directory / full).stat().st_size >= limit
    assert ids(directory) == {full: stored, new: []}
    # The rest of that second still goes to the full file, the next second to the new one.
    await files.add(at(last + 0.9), 10, 30, 7, "same second")
    await files.add(at(last + 1), 10, 30, 7, "next second")
    assert ids(directory) == {full: [*stored, at(last + 0.9)], new: [at(last + 1)]}


async def test_new_file_fails(
    open_files: Opener,
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: A new message file starts when the newest is full."""
    real = messages.create_file
    created: list[str] = []

    def create_file(path: Path) -> sqlite3.Connection:
        created.append(path.name)
        if len(created) == 2:
            message = "database or disk is full"
            raise sqlite3.OperationalError(message)
        return real(path)

    monkeypatch.setattr(messages, "create_file", create_file)
    files = await open_files(1)

    with caplog.at_level(logging.ERROR):
        await files.add(at(5), 10, 30, 7, "a")  # the first file, then its successor fails

    assert ids(directory) == {FIRST: [at(5)]}
    assert f"ChatLogger cannot start the message file {name(6)}" in caplog.text
    await files.add(at(10), 10, 30, 7, "b")  # still the newest file: it tries again
    assert ids(directory) == {FIRST: [at(5), at(10)], name(11): []}
    assert created == [FIRST, name(6), name(11)]


async def test_leftover_temporary_file(open_files: Opener, directory: Path) -> None:
    """Requirement: A new message file starts when the newest is full."""
    directory.mkdir(parents=True)
    leftover = directory / f"{FIRST}.tmp"
    leftover.write_bytes(b"left by an attempt that failed")
    files = await open_files()

    await files.add(at(5), 10, 30, 7, "a")

    assert rows(directory) == {FIRST: [(at(5), 10, 30, 7, "a", 0)]}
    assert not leftover.exists()


async def test_new_file_fails_after_its_rename(
    open_files: Opener,
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: A new message file starts when the newest is full."""
    real = messages.connect

    def connect(path: Path) -> sqlite3.Connection:
        if path.name == name(6):  # the new file, once renamed
            message = "unable to open database file"
            raise sqlite3.OperationalError(message)
        return real(path)

    monkeypatch.setattr(messages, "connect", connect)
    files = await open_files(1)

    with caplog.at_level(logging.ERROR):
        await files.add(at(5), 10, 30, 7, "a")

    # A file that the open files leave out would hold this range at the next start, away from
    # the messages that the full file takes meanwhile.
    assert ids(directory) == {FIRST: [at(5)]}
    assert f"ChatLogger cannot start the message file {name(6)}" in caplog.text
    await files.add(at(10), 10, 30, 7, "b")
    assert ids(directory) == {FIRST: [at(5), at(10)], name(11): []}


async def test_close_after_the_work_under_way(open_files: Opener, directory: Path) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    files = await open_files()
    adding = asyncio.create_task(files.add(at(5), 10, 30, 7, "a"))
    await asyncio.sleep(0)  # the insert waits on the files' thread

    await files.close()
    await adding

    assert not files.is_open
    assert rows(directory) == {FIRST: [(at(5), 10, 30, 7, "a", 0)]}


async def test_after_closing(open_files: Opener, directory: Path) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    files = await open_files()
    await files.add(at(5), 10, 30, 7, "a")
    await files.close()

    with pytest.raises(RuntimeError, match="closed"):
        await files.add(at(6), 10, 30, 7, "b")
    with pytest.raises(RuntimeError, match="closed"):
        await files.pop(at(5))
    await files.close()  # once more: nothing to do

    assert rows(directory) == {FIRST: [(at(5), 10, 30, 7, "a", 0)]}


async def test_corrupt_file(open_files: Opener, directory: Path) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    files = await open_files()
    await files.add(at(5), 10, 30, 7, "a")
    await files.close()
    garbage = directory / name(60)
    garbage.write_bytes(b"not a database " * 100)

    broken = MessageFiles(directory, MIB)
    with pytest.raises(sqlite3.DatabaseError):
        await broken.open()
    gc.collect()  # a connection left open would warn here, and the warning fails the test

    assert not broken.is_open
    assert garbage.read_bytes() == b"not a database " * 100
