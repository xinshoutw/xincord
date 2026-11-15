"""The feed's loop: from READY until the plugin unloads, over one session."""

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
import pytest

from bulletin_fakes import NOW
from plugin_fakes import WAIT
from xincord.plugins.ntust_announcements.cog import NtustAnnouncements, utc_now
from xincord.plugins.ntust_announcements.state import State, States

if TYPE_CHECKING:
    from conftest import Scene
    from plugin_fakes import Ready
    from xincord.core.bot import Bot
    from xincord.core.storage import Store

LOGGER = "xincord.plugins.ntust_announcements"
PLACEHOLDERS = """\
boards:
  - name: STUDENT_DORMITORY
    board: "1053-1436"
    channel-id: 0
  - name: STUDENT_AFFAIRS
    board: "1053"
    channel-id: 0
"""
# Nothing listens on port 9 of this machine.
UNREACHABLE = """\
api-url: "http://127.0.0.1:9/secret-path/api/v1"
boards:
  - name: STUDENT_DORMITORY
    board: "1053-1436"
    channel-id: 101
"""


async def started(scene: Scene) -> None:
    """READY, then the first pass, which finds the feed's end; the loop then waits."""
    scene.ready.set()
    await scene.waits.asleep(1)


async def test_start_at_ready(scene: Scene) -> None:
    """Requirement: The feed is read from READY until the plugin unloads."""
    await scene.ready.waiters(1)
    assert (scene.opened, scene.api.reads) == ([], [])

    await started(scene)

    assert scene.opened == ["https://bulletin.ntust.org/api/v1"]
    assert scene.api.reads == [0]


async def test_interval(scene: Scene) -> None:
    """Requirement: The feed is read from READY until the plugin unloads."""
    await started(scene)
    await scene.waits.wake()
    await scene.waits.asleep(2)

    assert scene.waits.waits == [60, 60]
    assert scene.api.reads == [0, 0]


async def test_unload(scene: Scene) -> None:
    """Requirement: The feed is read from READY until the plugin unloads."""
    await started(scene)

    await scene.bot.unload_extension("xincord.plugins.ntust_announcements")
    await scene.waits.wake()

    assert scene.closed == 1
    assert scene.api.reads == [0]


async def test_no_pings(scene: Scene, store: Store) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    await States(store).save(State(0))
    scene.api.publish(1, title="@everyone dormitory notice", link_item=True)

    await started(scene)

    [fields] = scene.posts(101)
    assert "@everyone" in str(fields["content"])
    mentions = fields["allowed_mentions"]
    assert isinstance(mentions, discord.AllowedMentions)
    assert mentions.to_dict() == discord.AllowedMentions.none().to_dict()


def test_utc_now() -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    assert utc_now().utcoffset() == timedelta(0)  # comparable with the feed's times


async def test_the_clock(scene: Scene, store: Store) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    await States(store).save(State(0))
    scene.api.publish(1, at=NOW)
    scene.clock.value = NOW.replace(hour=2)  # an hour later

    await started(scene)

    assert len(scene.posts(101)) == 1


@pytest.mark.parametrize("config", [PLACEHOLDERS])
async def test_no_channel_yet(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config names the feed and the boards."""
    caplog.set_level(logging.INFO)
    scene.ready.set()
    scene.cog.check()

    assert scene.cog.tasks == ()
    assert (
        "NtustAnnouncements: 2 boards have no channel yet: STUDENT_DORMITORY, STUDENT_AFFAIRS"
        in caplog.messages
    )


@pytest.mark.parametrize("config", [UNREACHABLE])
async def test_origin_only(bot: Bot, ready: Ready, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding."""
    slept = asyncio.Event()

    async def sleep(_: float) -> None:
        slept.set()
        await asyncio.Event().wait()  # until the test ends

    cog = bot.get_cog("NtustAnnouncements")
    assert isinstance(cog, NtustAnnouncements)
    cog.sleep = sleep
    ready.set()
    async with asyncio.timeout(WAIT):
        await slept.wait()

    [warning] = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == logging.WARNING
    ]
    assert "http://127.0.0.1:9 failed" in warning
    assert "secret-path" not in warning
