"""Pending notices end with the plugin: unloading or reloading it cancels their wait.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:31-37
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import WAIT

if TYPE_CHECKING:
    from conftest import Scene


async def test_unload_during_the_wait(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Pending notices end with the plugin."""
    await scene.create(31, "ticket-alice")
    await scene.clock.asleep()
    cog = scene.cog
    [notice] = cog.notices

    with caplog.at_level(logging.WARNING):
        # What an unload or a reload does to the cog; v3's queueAfter could not be cancelled.
        await scene.bot.remove_cog("TicketAwayNotice")
        scene.clock.wake()
        async with asyncio.timeout(WAIT):
            await asyncio.gather(notice, return_exceptions=True)

    assert notice.cancelled()
    assert cog.notices == set()
    assert scene.notices() == []
    assert caplog.records == []


@pytest.mark.xfail(strict=True, reason="Pending notices end with the plugin")
async def test_event_after_the_unload(scene: Scene) -> None:
    """Requirement: Pending notices end with the plugin."""
    cog = scene.cog
    await scene.bot.remove_cog("TicketAwayNotice")
    await scene.create(31, "ticket-alice")  # parsed after the unload: no listener runs any more
    guild = scene.bot.get_guild(10)
    assert guild is not None
    channel = guild.get_channel(31)
    assert channel is not None

    # discord.py runs each listener as a task, so one that it scheduled before the unload runs
    # after cog_unload.
    await cog.on_guild_channel_create(channel)
    scene.clock.wake()
    async with asyncio.timeout(WAIT):
        await asyncio.gather(*cog.notices)

    assert scene.clock.delays == []
    assert scene.notices() == []
