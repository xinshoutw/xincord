"""The stored messages: one row per message in the plugin's table of the shared store.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:16-188
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterable

    from xincord.core.storage import Store

BATCH = 1000  # the messages that one transaction of the retention deletes at most

# v3 kept one table per channel, named by its ID, in one file per guild; one table holds them all,
# with v3's columns, so that the deferred migration can copy v3's rows. A message ID is unique,
# and its time drives the retention.
SCHEMA = (
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
FIND = "SELECT message, user_id, update_count FROM ChatLogger_messages WHERE message_id = ?"
DELETE = "DELETE FROM ChatLogger_messages WHERE message_id = ?"
# The oldest messages below an ID, a batch at a time (SQLite's DELETE takes no LIMIT by default).
PRUNE = (
    "DELETE FROM ChatLogger_messages WHERE message_id IN (SELECT message_id"
    " FROM ChatLogger_messages WHERE message_id < ? ORDER BY message_id LIMIT ?)"
)


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

    async def create(self) -> None:
        """Create the table and its index, unless they exist."""

        def create(db: sqlite3.Connection) -> None:
            for statement in SCHEMA:
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
            row = db.execute(FIND, (message_id,)).fetchone()
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
                row = db.execute(FIND, (message_id,)).fetchone()
                if row is not None:
                    db.execute(DELETE, (message_id,))
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
            deleted = await self.store.run(lambda db: db.execute(PRUNE, (before, batch)).rowcount)
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
