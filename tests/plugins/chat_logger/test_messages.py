"""The stored messages in the plugin's table of the shared store.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:16-188
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from discord.utils import time_snowflake

from xincord.plugins.chat_logger.messages import Edit, MessageLog, Stored

if TYPE_CHECKING:
    from xincord.core.storage import Store

type Row = tuple[int, int, int, int, str, int]  # v3's columns, with the guild and the channel

NOW = datetime(2026, 10, 10, tzinfo=UTC)


async def rows(store: Store) -> list[Row]:
    """The stored rows, by message ID."""
    found = await store.run(
        lambda db: db.execute(
            "SELECT message_id, guild_id, channel_id, user_id, message, update_count"
            " FROM ChatLogger_messages ORDER BY message_id"
        ).fetchall()
    )
    return [tuple(row) for row in found]


async def log(store: Store) -> MessageLog:
    """The message log over ``store``, with its table created."""
    created = MessageLog(store)
    await created.create()
    return created


def at(days: float) -> int:
    """The ID of a message created ``days`` days before ``NOW``."""
    return time_snowflake(NOW - timedelta(days=days))


async def test_table(store: Store) -> None:
    """Requirement: Guild messages are stored."""
    await log(store)
    await log(store)  # once: the table is kept

    columns = await store.run(
        lambda db: [row[1] for row in db.execute("PRAGMA table_info(ChatLogger_messages)")]
    )
    # v3's columns stay, so that the deferred migration can copy v3's rows.
    assert columns == ["message_id", "guild_id", "channel_id", "user_id", "message", "update_count"]


async def test_add(store: Store) -> None:
    """Requirement: Guild messages are stored."""
    messages = await log(store)

    await messages.add(100, 10, 30, 7, "hello")
    await messages.add(100, 10, 30, 7, "again")  # a replayed event keeps the first row
    await messages.add(101, 10, 41, 8, "")

    assert await rows(store) == [(100, 10, 30, 7, "hello", 0), (101, 10, 41, 8, "", 0)]


async def test_edit(store: Store) -> None:
    """Requirement: Edits of stored messages are logged."""
    messages = await log(store)
    await messages.add(100, 10, 30, 7, "hello")

    assert await messages.edit(100, "hi") == Edit(before="hello", user_id=7, count=1)
    assert await messages.edit(100, "hey") == Edit(before="hi", user_id=7, count=2)
    assert await messages.edit(100, "hey") is None  # the same text: nothing changes
    assert await messages.edit(200, "hi") is None  # not stored: not stored on an edit either
    assert await rows(store) == [(100, 10, 30, 7, "hey", 2)]


async def test_pop(store: Store) -> None:
    """Requirement: Deletions of stored messages are logged."""
    messages = await log(store)
    await messages.add(100, 10, 30, 7, "hello")
    await messages.edit(100, "hi")

    assert await messages.pop(100) == Stored(text="hi", user_id=7, count=1)
    assert await messages.pop(100) is None  # v3 kept the text of deleted messages
    assert await rows(store) == []


async def test_pop_all(store: Store) -> None:
    """Requirement: Deletions of stored messages are logged."""
    messages = await log(store)
    for message_id, text in ((102, "c"), (100, "a"), (101, "b"), (103, "d")):
        await messages.add(message_id, 10, 30, 7, text)

    taken = await messages.pop_all([102, 104, 100, 101])

    assert taken == [  # oldest first; 104 is not stored
        (100, Stored("a", 7, 0)),
        (101, Stored("b", 7, 0)),
        (102, Stored("c", 7, 0)),
    ]
    assert await rows(store) == [(103, 10, 30, 7, "d", 0)]


async def test_prune(store: Store) -> None:
    """Requirement: Stored messages are kept for the retention period."""
    messages = await log(store)
    old = [at(40), at(35), at(31), at(30.5), at(30.1)]
    kept = [at(29), at(1)]
    for message_id in (*kept, *old):
        await messages.add(message_id, 10, 30, 7, "text")

    # Two at a time, so that one deletion never holds the store long.
    assert await messages.prune(at(30), batch=2) == 5
    assert [row[0] for row in await rows(store)] == kept
    assert await messages.prune(at(30), batch=2) == 0


async def test_forget(store: Store) -> None:
    """Requirement: Data is forgotten with the guild."""
    messages = await log(store)
    await messages.add(100, 20, 30, 7, "a")
    await messages.add(101, 10, 31, 7, "b")
    await messages.add(102, 20, 32, 7, "c")

    assert await messages.guild_ids() == [10, 20]
    assert await messages.forget(20) == 2
    assert await messages.guild_ids() == [10]
    assert await messages.forget(20) == 0
    assert await rows(store) == [(101, 10, 31, 7, "b", 0)]
