"""Requirement: Status rotation.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/statuschanger/StatusChanger.kt:16-90
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import discord
import pytest

from plugin_fakes import until, watch_syncs, write_config
from xincord.core.bot import Bot
from xincord.core.config import Activity, ActivityType, CoreConfig, Status
from xincord.core.status import activity, rotate

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xincord.core.storage import Store

FAST = 0.01


def entry(kind: str, text: str, seconds: float = FAST, url: str | None = None) -> Activity:
    return Activity(type=ActivityType(kind), text=text, seconds=seconds, url=url)


def test_activity_kinds() -> None:
    streaming = activity(entry("streaming", "Live", url="https://twitch.tv/x"))
    custom = activity(entry("custom", "Hi"))

    assert isinstance(streaming, discord.Streaming)
    assert (streaming.name, streaming.url) == ("Live", "https://twitch.tv/x")
    assert isinstance(custom, discord.CustomActivity)
    assert custom.name == "Hi"
    for kind in ("playing", "listening", "watching", "competing"):
        converted = activity(entry(kind, "Text"))
        assert isinstance(converted, discord.Activity)
        assert (converted.type, converted.name) == (discord.ActivityType[kind], "Text")


class Presence:
    """Records ``change_presence`` calls; fails the calls whose index is in ``failing``."""

    def __init__(self, *failing: int) -> None:
        self.shown: list[str | None] = []
        self.failing = failing

    async def change_presence(self, *, activity: discord.BaseActivity | None = None) -> None:
        self.shown.append(getattr(activity, "name", None))
        if len(self.shown) - 1 in self.failing:
            raise discord.ClientException


async def rotated(activities: Sequence[Activity], presence: Presence, calls: int) -> None:
    """Rotate until ``presence`` saw ``calls`` updates or the rotation ended."""
    client = cast("discord.Client", SimpleNamespace(change_presence=presence.change_presence))
    task = asyncio.create_task(rotate(client, activities))
    await until(lambda: len(presence.shown) >= calls or task.done())
    if task.done():
        task.result()  # surface the rotation's own error
    else:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_rotation() -> None:
    two, one, none = Presence(), Presence(), Presence()

    await rotated([entry("playing", "A"), entry("watching", "B")], two, calls=5)
    await rotated([entry("playing", "Only", seconds=60)], one, calls=2)
    await rotated([], none, calls=1)

    assert two.shown[:5] == ["A", "B", "A", "B", "A"]
    assert one.shown == ["Only"]
    assert none.shown == []


async def test_failed_update(caplog: pytest.LogCaptureFixture) -> None:
    presence = Presence(0)

    await rotated([entry("playing", "A"), entry("playing", "B")], presence, calls=2)

    assert presence.shown[:2] == ["A", "B"]
    assert "A" in caplog.text


@pytest.mark.usefixtures("installed")
async def test_bot_rotation(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    config = CoreConfig(status=Status(activities=(entry("playing", "A"), entry("playing", "B"))))
    bot = Bot([], root=Path("plugins"), store=store, config=config)
    presence = Presence()

    async def change_presence(_self: Bot, *, activity: discord.BaseActivity | None = None) -> None:
        await presence.change_presence(activity=activity)

    monkeypatch.setattr(Bot, "change_presence", change_presence)
    watch_syncs(bot, store, monkeypatch)

    def ready(_: Bot) -> bool:
        return True

    monkeypatch.setattr(Bot, "is_ready", ready)

    await bot.on_ready()
    await bot.on_ready()  # a reconnect keeps the running rotation
    await until(lambda: len(presence.shown) >= 4)
    assert presence.shown[:4] == ["A", "B", "A", "B"]

    write_config("status:\n  activities: [{type: watching, text: New, seconds: 60}]\n")
    assert await bot.reload() == "Reloaded: none."
    await until(lambda: presence.shown[-1] == "New")

    await bot.close()
    seen = len(presence.shown)
    await asyncio.sleep(3 * FAST)
    assert len(presence.shown) == seen
