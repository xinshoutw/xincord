"""Where the plugin keeps the stored messages: its own files under ``data/ChatLogger/``.

v3 kept one file per guild, ``plugins/ChatLogger/data/<guildId>.db``, with one table per channel,
through SQLiteAPI's connections, which it never closed.
"""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from discord.utils import time_snowflake

import payloads
from plugin_fakes import unclosed
from xincord.core.bot import Bot
from xincord.plugins.chat_logger.messages import MessageFiles

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from conftest import Loader, Scene
    from xincord.core.storage import Store

    type WriteFile = Callable[[datetime, Sequence[int]], str]

# The scenes' messages have small IDs, created at Discord's epoch, the first second of 2015.
EPOCH_FILE = "messages-20150101T000000Z.db"
NOON = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)
LONG = "x" * 4000  # about a page of a file


def at(seconds: float) -> int:
    """The ID of a message created ``seconds`` after noon."""
    return time_snowflake(NOON + timedelta(seconds=seconds))


def record_opens(monkeypatch: pytest.MonkeyPatch) -> list[MessageFiles]:
    """The message files that the plugin opens from now on, in order."""
    opened: list[MessageFiles] = []
    real_open = MessageFiles.open

    async def open_files(files: MessageFiles) -> None:
        opened.append(files)
        await real_open(files)

    monkeypatch.setattr(MessageFiles, "open", open_files)
    return opened


def no_leak(opened: list[MessageFiles]) -> None:
    """Let the files go and check that no connection was left open."""
    opened.clear()
    assert unclosed() == []


async def test_first_file(scene: Scene) -> None:
    """Requirement: Stored messages live in the plugin's own files."""
    assert scene.files() == {}  # no message, no file

    await scene.send(100, 30, "hello")

    assert scene.files() == {EPOCH_FILE: [100]}


async def test_old_table(store: Store, load: Loader) -> None:
    """Requirement: Stored messages live in the plugin's own files."""

    def earlier_version(db: sqlite3.Connection) -> None:
        db.execute(
            "CREATE TABLE ChatLogger_messages (message_id INTEGER PRIMARY KEY, guild_id INTEGER,"
            " channel_id INTEGER, user_id INTEGER, message TEXT, update_count INTEGER)"
        )
        db.execute("CREATE INDEX ChatLogger_messages_guild ON ChatLogger_messages (guild_id)")
        db.execute("INSERT INTO ChatLogger_messages VALUES (1, 10, 30, 7, 'old', 0)")

    await store.run(earlier_version)

    await load()

    names = await store.run(
        lambda db: [row[0] for row in db.execute("SELECT name FROM sqlite_master")]
    )
    assert [name for name in names if name.startswith("ChatLogger")] == []


@pytest.mark.parametrize("config", ["max_file_size_mb: 1\n"])
async def test_messages_of_older_files(scene: Scene) -> None:
    """Requirement: A new message file starts when the newest is full."""
    await scene.listen(5, [30])
    old: list[int] = []
    for second in range(600):  # 1 MiB takes about 250 long messages
        old.append(at(second))
        await scene.cog.messages.add(old[-1], 10, 30, 7, LONG)
        if len(scene.files()) > 1:
            break
    new = at(len(old))  # the second after the message that filled the first file

    await scene.send(new, 30, "new")

    assert list(scene.files().values()) == [old, [new]]
    await scene.edit(old[0], 30, "first, edited")
    await scene.edit(new, 30, "new, edited")
    scene.rest.answers["GET /guilds/10/members/7"] = [payloads.member(7, "user7")] * 2
    await scene.delete(old[0], 30)
    await scene.delete(new, 30)
    assert len(scene.posts(5)) == 4  # each found in its own file
    assert list(scene.files().values()) == [old[1:], []]


async def test_unload(scene: Scene) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    cog = scene.cog
    sending = asyncio.create_task(scene.send(100, 30, "hello"))
    await asyncio.sleep(0)  # the insert waits on the files' thread

    await scene.bot.remove_cog("ChatLogger")  # cog_unload, as an unload or a reload runs it
    await sending

    assert not cog.messages.is_open
    assert scene.files() == {EPOCH_FILE: [100]}


async def test_reload(scene: Scene) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")
    previous = scene.cog

    assert await scene.bot.reload_plugin("ChatLogger") == ["ChatLogger"]

    assert not previous.messages.is_open
    assert scene.cog is not previous
    assert scene.cog.messages.is_open
    await scene.edit(100, 30, "hi")  # the new version finds the message stored before
    assert len(scene.posts(5)) == 1
    del previous
    assert unclosed() == []  # no connection of the previous version is left open


async def test_failed_load(
    store: Store, load: Loader, write_file: WriteFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    write_file(NOON, [at(0)])  # a file for the load to open
    opened = record_opens(monkeypatch)

    def is_ready(_bot: Bot) -> bool:
        return True

    async def failing(namespace: str) -> list[str]:
        message = f"cannot read {namespace}"
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(Bot, "is_ready", is_ready)  # a reload: the guilds are checked at once
    monkeypatch.setattr(store, "keys", failing)

    bot = await load()

    assert bot.loaded == ()
    assert [files.is_open for files in opened] == [False]
    no_leak(opened)


async def test_setup_fails_after_the_cog(
    load: Loader, write_file: WriteFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    write_file(NOON, [at(0)])
    opened = record_opens(monkeypatch)

    def refuse(_bot: Bot, name: str) -> None:
        message = f"cannot relay {name}"
        raise RuntimeError(message)

    monkeypatch.setattr(Bot, "relay_gateway_event", refuse)  # the last step of setup

    bot = await load()

    assert bot.loaded == ()
    assert [files.is_open for files in opened] == [False]  # discord.py removed the cog
    no_leak(opened)


async def test_bot_close(
    load: Loader, write_file: WriteFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The message files are open while the plugin is loaded."""
    write_file(NOON, [at(0)])
    opened = record_opens(monkeypatch)
    bot = await load()

    await bot.close()  # a stop, and the end of --no-online's check

    assert [files.is_open for files in opened] == [False]
    no_leak(opened)
