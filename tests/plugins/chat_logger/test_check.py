"""Channels that a guild no longer has are dropped from its lists when the bot is ready.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/JsonManager.kt:29-58
"""

import logging
from typing import TYPE_CHECKING

import payloads
from discord_fakes import forbidden, not_found
from plugin_fakes import dispatch
from xincord.plugins.chat_logger.cog import NAMESPACE
from xincord.plugins.listen_channels.settings import Setting
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    import pytest

    from conftest import Scene


async def test_deleted_channels(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    settings = ListenSettings(scene.store, NAMESPACE)
    # Guild 10 has channels 30 and 33, categories 20 and 21 and thread 41 of channel 30; channel
    # 31 and category 22 are gone.
    await settings.add_channels(10, 5, "allow", [30, 31, 41])
    await settings.add_channels(10, 5, "block", [22])
    await settings.add_channels(10, 6, "allow", [20])
    scene.rest.errors["GET /channels/31"] = not_found()
    scene.rest.errors["GET /channels/22"] = not_found()

    with caplog.at_level(logging.INFO):
        await dispatch(scene.bot, "ready")

    # A thread that discord.py caches stays, as JDA's lookup found cached threads.
    assert await settings.read_settings(10) == {
        5: Setting(allow=(30, 41)),
        6: Setting(allow=(20,)),
    }
    assert "ChatLogger dropped the deleted channels 31, 22 from the lists of guild (10)" in (
        caplog.text
    )


async def test_archived_threads(scene: Scene) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    settings = ListenSettings(scene.store, NAMESPACE)
    # discord.py does not cache archived threads: thread 42 of channel 32 is archived, thread 43 is
    # gone, and Discord refuses to show the private thread 44.
    await settings.add_channels(10, 5, "allow", [30, 42, 44])
    await settings.add_channels(10, 6, "block", [43, 42])
    scene.rest.answers["GET /channels/42"] = [
        payloads.thread(42, 32, 10),
        payloads.thread(42, 32, 10),
    ]
    scene.rest.errors["GET /channels/43"] = not_found()
    scene.rest.errors["GET /channels/44"] = forbidden()

    await dispatch(scene.bot, "ready")

    # v3 never logged threads, so dropping the uncached ones changed nothing there.
    assert await settings.read_settings(10) == {
        5: Setting(allow=(30, 42, 44)),
        6: Setting(block=(42,)),
    }
