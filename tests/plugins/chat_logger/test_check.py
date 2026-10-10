"""Channels that a guild no longer has are dropped from its lists when the bot is ready.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/JsonManager.kt:29-58
"""

import logging
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import dispatch
from xincord.plugins.chat_logger.cog import NAMESPACE
from xincord.plugins.listen_channels.settings import Setting
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    from conftest import Scene


@pytest.mark.xfail(strict=True, reason="Settings are checked when the bot is ready")
async def test_deleted_channels(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    settings = ListenSettings(scene.store, NAMESPACE)
    # Guild 10 has channels 30 and 33, categories 20 and 21 and thread 41 of channel 30; channel
    # 31 and category 22 are gone.
    await settings.add_channels(10, 5, "allow", [30, 31, 41])
    await settings.add_channels(10, 5, "block", [22])
    await settings.add_channels(10, 6, "allow", [20])

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
