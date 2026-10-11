"""The posts to the listen channels: the guild's locale, and channels that are gone or refuse."""

import logging
from typing import TYPE_CHECKING

import discord

import payloads
from discord_fakes import FakeChannel, forbidden, not_found, server_error
from plugin_fakes import golden
from xincord.plugins.chat_logger.cog import NAMESPACE
from xincord.plugins.listen_channels.settings import Setting
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    import pytest

    from conftest import Scene

GOLDEN = golden("chat_logger")


async def test_locale_without_templates(scene: Scene) -> None:
    """Requirement: Logs reach every listen channel."""
    scene.guild.preferred_locale = discord.Locale.french
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")

    await scene.edit(100, 30, "hi")

    assert scene.posts(5) == [GOLDEN["update"]["zh-TW"]]  # the fallback locale


async def test_deleted_listen_channel(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs reach every listen channel."""
    scene.channels[5] = FakeChannel(id=5, error=not_found())
    await scene.listen(5, [30])
    await scene.listen(6, [30])
    await scene.send(100, 30, "hello")

    with caplog.at_level(logging.INFO):
        await scene.edit(100, 30, "hi")

    # The other listen channels still get the log.
    assert len(scene.posts(6)) == 1
    settings = ListenSettings(scene.store, NAMESPACE)
    assert await settings.read_settings(10) == {6: Setting(allow=(30,))}
    assert "ChatLogger forgot the listen channel 5 of guild (10)" in caplog.text


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


async def test_bulk_deletion(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs reach every listen channel."""
    scene.channels[5] = FakeChannel(id=5, error=not_found())
    scene.channels[6] = FakeChannel(id=6, error=forbidden())
    for listen in (5, 6, 7):
        await scene.listen(listen, [30])
    for message_id in (100, 101, 102):
        await scene.send(message_id, 30, f"spam {message_id}")
    scene.rest.answers["GET /guilds/10/members/7"] = [payloads.member(7, "user7")]

    with caplog.at_level(logging.INFO):
        await scene.delete_all([100, 101, 102], 30)

    # A purge does not retry a listen channel that is gone or refuses, once per message.
    assert len(scene.posts(7)) == 3
    assert caplog.text.count("forgot the listen channel 5 ") == 1
    assert caplog.text.count("cannot post in the listen channel 6 ") == 1


async def test_bulk_deletion_and_a_failing_listen_channel(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Logs reach every listen channel."""
    scene.channels[5] = FakeChannel(id=5, error=server_error())
    await scene.listen(5, [30])
    for message_id in (100, 101):
        await scene.send(message_id, 30, f"spam {message_id}")
    scene.rest.answers["GET /guilds/10/members/7"] = [payloads.member(7, "user7")]

    await scene.delete_all([100, 101], 30)

    # Discord's failure may pass: the next message tries the channel again.
    assert caplog.text.count("cannot post in the listen channel 5 ") == 2
