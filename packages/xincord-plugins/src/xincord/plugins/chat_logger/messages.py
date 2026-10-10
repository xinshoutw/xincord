"""The stored messages: one row per message in the plugin's own files, ``data/ChatLogger/``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:16-188
    XsDiscordBotKt@3a59607:Plugins/API/SQLiteAPI/src/main/kotlin/api/sqlite/SQLiteFileManager.kt:8-46
"""

import asyncio
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .files import file_name, first_id, first_second, next_start, parse_name, route

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from datetime import datetime
    from pathlib import Path

    from xincord.core.storage import Store

logger = logging.getLogger(__name__)

BATCH = 1000  # the messages that one transaction of the retention deletes at most

# v3 kept one table per channel, named by its ID, in one file per guild; one table holds them all,
# with v3's columns, so that the deferred migration can copy v3's rows. A message ID is unique,
# and its time drives the retention.
STORE_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS ChatLogger_messages (
        message_id INTEGER PRIMARY KEY,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        update_count INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ChatLogger_messages_guild ON ChatLogger_messages (guild_id)",
)
STORE_FIND = "SELECT message, user_id, update_count FROM ChatLogger_messages WHERE message_id = ?"
STORE_DELETE = "DELETE FROM ChatLogger_messages WHERE message_id = ?"
# The oldest messages below an ID, a batch at a time (SQLite's DELETE takes no LIMIT by default).
STORE_PRUNE = (
    "DELETE FROM ChatLogger_messages WHERE message_id IN (SELECT message_id"
    " FROM ChatLogger_messages WHERE message_id < ? ORDER BY message_id LIMIT ?)"
)

# Each message file holds one table with v3's columns, plus the guild and the channel, which v3
# took from its file and table names, so that the import of v3's files can copy v3's rows.
SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        update_count INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS messages_guild ON messages (guild_id)",
)
INSERT = (
    "INSERT OR IGNORE INTO messages"
    " (message_id, guild_id, channel_id, user_id, message, update_count)"
    " VALUES (?, ?, ?, ?, ?, 0)"
)
FIND = "SELECT message, user_id, update_count FROM messages WHERE message_id = ?"
UPDATE = "UPDATE messages SET message = ?, update_count = ? WHERE message_id = ?"
DELETE = "DELETE FROM messages WHERE message_id = ?"
# The oldest messages below an ID, a batch at a time (SQLite's DELETE takes no LIMIT by default).
PRUNE = (
    "DELETE FROM messages WHERE message_id IN"
    " (SELECT message_id FROM messages WHERE message_id < ? ORDER BY message_id LIMIT ?)"
)
FORGET = "DELETE FROM messages WHERE guild_id = ?"
GUILDS = "SELECT DISTINCT guild_id FROM messages"
LAST = "SELECT max(message_id) FROM messages"


@dataclass(frozen=True)
class Stored:
    """A stored message: its latest text, its author, and how often its text changed."""

    text: str
    user_id: int
    count: int


@dataclass(frozen=True)
class Edit:
    """A stored message's new text: the text before, the author, and the changes with this one."""

    before: str
    user_id: int
    count: int


class MessageLog:
    """The plugin's table of stored messages, ``ChatLogger_messages``, in the shared store.

    Each method is one transaction on the store's database thread, so concurrent handlers never
    lose an update.
    """

    def __init__(self, store: Store) -> None:
        """Keep the store whose database holds the table."""
        self.store = store

    @property
    def is_open(self) -> bool:
        """Whether the files are open."""
        raise NotImplementedError

    async def create(self) -> None:
        """Create the table and its index, unless they exist."""

        def create(db: sqlite3.Connection) -> None:
            for statement in STORE_SCHEMA:
                db.execute(statement)

        await self.store.run(create)

    async def add(
        self, message_id: int, guild_id: int, channel_id: int, user_id: int, text: str
    ) -> None:
        """Store a new message with no change counted.

        A message stored already keeps its row: a replayed gateway event changes nothing (v3's
        insert threw there).
        """
        row = (message_id, guild_id, channel_id, user_id, text)
        await self.store.run(
            lambda db: db.execute(
                "INSERT OR IGNORE INTO ChatLogger_messages"
                " (message_id, guild_id, channel_id, user_id, message, update_count)"
                " VALUES (?, ?, ?, ?, ?, 0)",
                row,
            )
        )

    async def edit(self, message_id: int, text: str) -> Edit | None:
        """Store a message's new text and count the change; return what the log shows.

        None when the message is not stored, as v3 ignored the edits of messages it had not
        stored, or when its text is the same: v3 counted every update, a pin or a link preview
        too.
        """

        def apply(db: sqlite3.Connection) -> Edit | None:
            row = db.execute(STORE_FIND, (message_id,)).fetchone()
            if row is None or row[0] == text:
                return None
            edit = Edit(before=row[0], user_id=row[1], count=row[2] + 1)
            db.execute(
                "UPDATE ChatLogger_messages SET message = ?, update_count = ? WHERE message_id = ?",
                (text, edit.count, message_id),
            )
            return edit

        return await self.store.run(apply)

    async def pop(self, message_id: int) -> Stored | None:
        """Take a deleted message out of the store and return it, or None if it is not stored.

        v3 kept the text of deleted messages; nothing needs it once the deletion is handled.
        """
        taken = await self.pop_all([message_id])
        return taken[0][1] if taken else None

    async def pop_all(self, message_ids: Iterable[int]) -> list[tuple[int, Stored]]:
        """Take the deleted messages of a bulk deletion out of the store and return them.

        They come oldest first, with their IDs; messages that are not stored are left out.
        """
        ids = sorted(set(message_ids))

        def take(db: sqlite3.Connection) -> list[tuple[int, Stored]]:
            taken: list[tuple[int, Stored]] = []
            for message_id in ids:
                row = db.execute(STORE_FIND, (message_id,)).fetchone()
                if row is not None:
                    db.execute(STORE_DELETE, (message_id,))
                    taken.append((message_id, Stored(text=row[0], user_id=row[1], count=row[2])))
            return taken

        return await self.store.run(take)

    async def prune(self, before: int, batch: int = BATCH) -> int:
        """Delete the messages whose IDs are below ``before``, ``batch`` at a time.

        Return how many were deleted. Each batch is its own transaction, so that the store's
        database thread, which serves every plugin, is never held long.
        """
        total = 0
        while True:
            deleted = await self.store.run(
                lambda db: db.execute(STORE_PRUNE, (before, batch)).rowcount
            )
            total += deleted
            if deleted < batch:
                return total

    async def forget(self, guild_id: int) -> int:
        """Delete a guild's messages; return how many there were."""
        return await self.store.run(
            lambda db: (
                db.execute(
                    "DELETE FROM ChatLogger_messages WHERE guild_id = ?", (guild_id,)
                ).rowcount
            )
        )

    async def guild_ids(self) -> list[int]:
        """Return the guilds with stored messages, in order."""
        rows = await self.store.run(
            lambda db: db.execute(
                "SELECT DISTINCT guild_id FROM ChatLogger_messages ORDER BY guild_id"
            ).fetchall()
        )
        return [row[0] for row in rows]


def create_file(path: Path) -> sqlite3.Connection:
    """Create the message file ``path`` with its table and return a connection to it.

    The file is built under a temporary name and renamed once complete, so that a file under a
    message file's name is always whole. SQLite's journal follows the path that a connection
    opened, so the file is renamed while no connection has it open.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    building = path.with_name(f"{path.name}.tmp")
    with closing(connect(building)):
        pass
    building.replace(path)
    return connect(path)


def connect(path: Path) -> sqlite3.Connection:
    """Open a message file, creating its table and index where they are missing.

    Raises:
        sqlite3.DatabaseError: The file is not a database; it is left as it is.
    """
    connection = sqlite3.connect(path, autocommit=False)
    try:
        for statement in SCHEMA:
            connection.execute(statement)
        connection.commit()
    except BaseException:
        connection.close()
        raise
    return connection


def transaction[T](connection: sqlite3.Connection, work: Callable[[sqlite3.Connection], T]) -> T:
    """Run ``work`` as one transaction of ``connection``: committed, or rolled back if it raises."""
    try:
        result = work(connection)
    except BaseException:
        connection.rollback()
        raise
    connection.commit()
    return result


@dataclass(frozen=True)
class MessageFile:
    """An open message file: its start, the first message ID it holds, its path, its connection."""

    start: datetime
    first_id: int
    path: Path
    connection: sqlite3.Connection


class MessageFiles:
    """The stored messages in the plugin's own SQLite files, ``messages-<start>.db``.

    Each file holds the messages created from its start up to the next file's (``files``); a new
    file starts when the newest reaches ``max_bytes``. The files are open between :meth:`open`
    and :meth:`close`, one connection each, on a thread of their own, the files' only writer; each
    method is one job there, so jobs never interleave, and each job's work in a file is one
    transaction.
    """

    def __init__(self, directory: Path, max_bytes: int) -> None:
        """Keep the directory of the files and the size from which a new file starts."""
        self.directory = directory
        self.max_bytes = max_bytes
        self._executor: ThreadPoolExecutor | None = None
        self._files: tuple[MessageFile, ...] = ()  # oldest first, on the files' thread only

    @property
    def is_open(self) -> bool:
        """Whether the files are open."""
        return self._executor is not None

    async def open(self) -> None:
        """Open the message files in the directory, creating the table where it is missing.

        Other files in the directory are left alone. No file is created before the first message.

        Raises:
            sqlite3.DatabaseError: A message file is not a database; it is left as it is, and no
                file stays open.
        """
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xincord-chat-logger")
        try:
            await asyncio.get_running_loop().run_in_executor(executor, self._open)
        except BaseException:
            executor.shutdown()
            raise
        self._executor = executor

    async def close(self) -> None:
        """Close the files after the work already under way; later work raises RuntimeError."""
        executor, self._executor = self._executor, None
        if executor is None:
            return
        try:
            await asyncio.get_running_loop().run_in_executor(executor, self._close)
        finally:
            executor.shutdown()

    async def add(
        self, message_id: int, guild_id: int, channel_id: int, user_id: int, text: str
    ) -> None:
        """Store a new message, with no change counted, in the file that holds its ID.

        A message stored already keeps its row: a replayed gateway event changes nothing (v3's
        insert threw there). A message stored in the newest file can start the next one.
        """
        await self._run(self._add, (message_id, guild_id, channel_id, user_id, text))

    async def edit(self, message_id: int, text: str) -> Edit | None:
        """Store a message's new text and count the change; return what the log shows.

        None when the message is not stored, as v3 ignored the edits of messages it had not
        stored, or when its text is the same: v3 counted every update, a pin or a link preview
        too.
        """
        return await self._run(self._edit, message_id, text)

    async def pop(self, message_id: int) -> Stored | None:
        """Take a deleted message out of its file and return it, or None if it is not stored.

        v3 kept the text of deleted messages; nothing needs it once the deletion is handled.
        """
        taken = await self.pop_all([message_id])
        return taken[0][1] if taken else None

    async def pop_all(self, message_ids: Iterable[int]) -> list[tuple[int, Stored]]:
        """Take the deleted messages of a bulk deletion out of their files and return them.

        They come oldest first, with their IDs; messages that are not stored are left out.
        """
        return await self._run(self._pop_all, sorted(set(message_ids)))

    async def prune(self, before: int, batch: int = BATCH) -> int:
        """Delete the messages whose IDs are below ``before``, ``batch`` at a time.

        Return how many were deleted. Each batch is its own job, so that the messages that arrive
        meanwhile are not held up long.
        """
        total = 0
        while deleted := await self._run(self._prune, before, batch):
            total += deleted
        return total

    async def forget(self, guild_id: int) -> int:
        """Delete a guild's messages from every file; return how many there were."""
        return await self._run(self._forget, guild_id)

    async def guild_ids(self) -> list[int]:
        """Return the guilds with stored messages, in order."""
        return await self._run(self._guild_ids)

    async def _run[*Args, T](self, job: Callable[[*Args], T], *args: *Args) -> T:
        """Run ``job`` on the files' thread, after the jobs before it."""
        if self._executor is None:
            message = "ChatLogger's message files are closed"
            raise RuntimeError(message)
        return await asyncio.get_running_loop().run_in_executor(self._executor, job, *args)

    # The jobs below run on the files' thread.

    def _open(self) -> None:
        found = sorted(
            (start, path)
            for path in (self.directory.iterdir() if self.directory.is_dir() else ())
            if (start := parse_name(path.name)) is not None
        )
        opened: list[MessageFile] = []
        try:
            for start, path in found:
                opened.append(MessageFile(start, first_id(start), path, connect(path)))
        except BaseException:
            for file in opened:
                file.connection.close()
            raise
        self._files = tuple(opened)

    def _close(self) -> None:
        files, self._files = self._files, ()
        for file in files:
            file.connection.close()

    def _holding(self, message_id: int) -> MessageFile | None:
        """The file whose range holds ``message_id``, or None before the first message."""
        if not self._files:
            return None
        return self._files[route([file.first_id for file in self._files], message_id)]

    def _add(self, row: tuple[int, int, int, int, str]) -> None:
        file = self._holding(row[0])
        if file is None:  # the first message: its second starts the first file
            file = self._create(first_second(row[0]))
            self._files = (file,)
        newest = file is self._files[-1]

        def insert(db: sqlite3.Connection) -> int | None:
            db.execute(INSERT, row)
            if not newest:
                return None
            pages = db.execute("PRAGMA page_count").fetchone()[0]
            size = db.execute("PRAGMA page_size").fetchone()[0]
            return db.execute(LAST).fetchone()[0] if pages * size >= self.max_bytes else None

        last_id = transaction(file.connection, insert)
        if last_id is not None:  # the newest file is full: the next one starts after it
            self._start_after(file, last_id)

    def _start_after(self, full: MessageFile, last_id: int) -> None:
        start = next_start(last_id, full.start)
        try:
            created = self._create(start)
        except sqlite3.Error, OSError:
            # The message is stored; the next message stored in the full file tries again.
            logger.exception("ChatLogger cannot start the message file %s", file_name(start))
            return
        self._files = (*self._files, created)
        logger.info("ChatLogger started the message file %s", created.path.name)

    def _create(self, start: datetime) -> MessageFile:
        path = self.directory / file_name(start)
        return MessageFile(start, first_id(start), path, create_file(path))

    def _edit(self, message_id: int, text: str) -> Edit | None:
        file = self._holding(message_id)
        if file is None:
            return None

        def apply(db: sqlite3.Connection) -> Edit | None:
            row = db.execute(FIND, (message_id,)).fetchone()
            if row is None or row[0] == text:
                return None
            edit = Edit(before=row[0], user_id=row[1], count=row[2] + 1)
            db.execute(UPDATE, (text, edit.count, message_id))
            return edit

        return transaction(file.connection, apply)

    def _pop_all(self, message_ids: list[int]) -> list[tuple[int, Stored]]:
        # The IDs are sorted, so the files come in order and their messages oldest first.
        by_file: dict[Path, tuple[MessageFile, list[int]]] = {}
        for message_id in message_ids:
            if (file := self._holding(message_id)) is not None:
                by_file.setdefault(file.path, (file, []))[1].append(message_id)
        taken: list[tuple[int, Stored]] = []
        for file, ids in by_file.values():
            taken += transaction(file.connection, lambda db, ids=ids: _take(db, ids))
        return taken

    def _prune(self, before: int, batch: int) -> int:
        """Delete up to ``batch`` messages below ``before`` from the oldest file holding any."""
        for file in self._files:
            deleted = transaction(
                file.connection, lambda db: db.execute(PRUNE, (before, batch)).rowcount
            )
            if deleted:
                return deleted
        return 0

    def _forget(self, guild_id: int) -> int:
        return sum(
            transaction(file.connection, lambda db: db.execute(FORGET, (guild_id,)).rowcount)
            for file in self._files
        )

    def _guild_ids(self) -> list[int]:
        found: set[int] = set()
        for file in self._files:
            rows = transaction(file.connection, lambda db: db.execute(GUILDS).fetchall())
            found.update(row[0] for row in rows)
        return sorted(found)


def _take(db: sqlite3.Connection, message_ids: list[int]) -> list[tuple[int, Stored]]:
    """Delete the stored messages of ``message_ids`` from one file and return them."""
    taken: list[tuple[int, Stored]] = []
    for message_id in message_ids:
        row = db.execute(FIND, (message_id,)).fetchone()
        if row is not None:
            db.execute(DELETE, (message_id,))
            taken.append((message_id, Stored(text=row[0], user_id=row[1], count=row[2])))
    return taken
