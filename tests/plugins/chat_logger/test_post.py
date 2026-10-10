"""The posts to the listen channels: the guild's locale, and channels that are gone or refuse.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:279-295
"""

import logging
from typing import TYPE_CHECKING

import discord
import pytest

from discord_fakes import FakeChannel, forbidden, not_found
from plugin_fakes import golden
from xincord.plugins.chat_logger.cog import NAMESPACE
from xincord.plugins.listen_channels.settings import Setting
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("chat_logger")
REASON = "Logs reach every listen channel"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_locale_without_templates(scene: Scene) -> None:
    """Requirement: Logs reach every listen channel."""
    scene.guild.preferred_locale = discord.Locale.french
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")

    await scene.edit(100, 30, "hi")

    assert scene.posts(5) == [GOLDEN["update"]["zh-TW"]]  # v3's fallback locale


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_deleted_listen_channel(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs reach every listen channel."""
    scene.channels[5] = FakeChannel(id=5, error=not_found())
    await scene.listen(5, [30])
    await scene.listen(6, [30])
    await scene.send(100, 30, "hello")

    with caplog.at_level(logging.INFO):
        await scene.edit(100, 30, "hi")

    # v3 stopped at the first missing listen channel, so the others got nothing.
    assert len(scene.posts(6)) == 1
    settings = ListenSettings(scene.store, NAMESPACE)
    assert await settings.read_settings(10) == {6: Setting(allow=(30,))}
    assert "ChatLogger forgot the listen channel 5 of guild (10)" in caplog.text


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_refused_listen_channel(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs reach every listen channel."""
    scene.channels[5] = FakeChannel(id=5, error=forbidden())
    await scene.listen(5, [30])
    await scene.listen(6, [30])
    await scene.send(100, 30, "hello")

    await scene.edit(100, 30, "hi")

    assert len(scene.posts(6)) == 1
    settings = ListenSettings(scene.store, NAMESPACE)
    assert sorted(await settings.read_settings(10)) == [5, 6]
    assert "ChatLogger cannot post in the listen channel 5 of guild (10)" in caplog.text
