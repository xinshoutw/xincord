"""The retention: messages older than ``retention_days`` leave the store, at READY and hourly.

v3 kept every message forever; there is no Kotlin counterpart.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:168-187
"""

import asyncio
import logging
import sqlite3
from datetime import timedelta
from typing import TYPE_CHECKING

from discord.utils import time_snowflake, utcnow

from plugin_fakes import WAIT
from xincord.core.bot import Bot

if TYPE_CHECKING:
    import pytest

    from conftest import Loader, Scene
    from plugin_fakes import Ready
    from xincord.core.storage import Store


class Hours:
    """The retention loop's sleep: each call is recorded, then waits until the test ends it."""

    def __init__(self) -> None:
        self.delays: list[float] = []
        self._asleep = asyncio.Event()
        self._wake = asyncio.Event()

    async def sleep(self, delay: float) -> None:
        """Record the delay, then wait for :meth:`pass_hour`."""
        self.delays.append(delay)
        self._asleep.set()
        await self._wake.wait()
        self._wake.clear()

    async def asleep(self) -> None:
        """Wait until the loop sleeps again."""
        async with asyncio.timeout(WAIT):
            await self._asleep.wait()
        self._asleep.clear()

    def pass_hour(self) -> None:
        """End the loop's sleep."""
        self._wake.set()


def ago(days: float) -> int:
    """The ID of a message created ``days`` days ago."""
    return time_snowflake(utcnow() - timedelta(days=days))


async def store_messages(scene: Scene, *message_ids: int) -> None:
    """Store messages of member 7 in channel 30 with the IDs given."""
    for message_id in message_ids:
        await scene.cog.messages.add(message_id, 10, 30, 7, "text")


async def stored(scene: Scene) -> list[int]:
    """The IDs of the stored messages."""
    return [row[0] for row in await scene.rows()]


async def test_old_messages(scene: Scene) -> None:
    """Requirement: Stored messages are kept for the retention period."""
    old, recent = ago(1827), ago(1825)
    await store_messages(scene, old, recent)

    await scene.cog.prune()  # retention_days 1826 (5 years), the bundled default

    assert await stored(scene) == [recent]


async def test_every_hour(scene: Scene, ready: Ready) -> None:
    """Requirement: Stored messages are kept for the retention period."""
    hours = Hours()
    scene.cog.sleep = hours.sleep
    [loop] = scene.cog.tasks  # started when the plugin loaded
    first, second, recent = ago(1900), ago(1850), ago(1)
    await store_messages(scene, first, recent)

    await ready.waiters(1)  # nothing is deleted before READY, as under --no-online
    assert await stored(scene) == [first, recent]
    ready.set()
    await hours.asleep()
    assert await stored(scene) == [recent]
    await store_messages(scene, second)
    hours.pass_hour()
    await hours.asleep()

    assert await stored(scene) == [recent]
    assert hours.delays == [3600, 3600]
    assert not loop.done()


async def test_failure(
    scene: Scene, ready: Ready, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Stored messages are kept for the retention period."""
    hours = Hours()
    scene.cog.sleep = hours.sleep
    [loop] = scene.cog.tasks
    calls: list[int] = []

    async def failing(before: int) -> int:
        calls.append(before)
        message = "database is locked"
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(scene.cog.messages, "prune", failing)
    ready.set()
    await hours.asleep()
    hours.pass_hour()
    await hours.asleep()

    assert len(calls) == 2  # the loop goes on
    days = scene.cog.config.retention_days
    assert f"ChatLogger cannot delete the messages older than {days} days" in caplog.text
    assert caplog.records[-1].levelno == logging.ERROR
    assert not loop.done()


async def test_unload(scene: Scene, ready: Ready) -> None:
    """Requirement: Stored messages are kept for the retention period."""
    hours = Hours()
    scene.cog.sleep = hours.sleep
    [loop] = scene.cog.tasks
    ready.set()
    await hours.asleep()

    await scene.bot.remove_cog("ChatLogger")  # runs cog_unload, as an unload or a reload does

    assert loop.cancelled()


async def test_failed_load(store: Store, load: Loader, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Stored messages are kept for the retention period."""

    def is_ready(_bot: Bot) -> bool:
        return True

    async def failing(namespace: str) -> list[str]:
        message = f"cannot read {namespace}"
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(Bot, "is_ready", is_ready)  # a reload: the guilds are checked at once
    monkeypatch.setattr(store, "keys", failing)

    bot = await load()

    assert bot.loaded == ()
    assert [task for task in asyncio.all_tasks() if task.get_name() == "ChatLogger retention"] == []
