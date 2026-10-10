"""Channels that a guild no longer has are dropped from its lists when the bot is ready.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/JsonManager.kt:29-58
"""

import logging
from typing import TYPE_CHECKING

import discord

from discord_fakes import FakeChannel, FakeGuild, FakeVoiceChannel
from plugin_fakes import dispatch, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.voice_logger.settings import Setting
from xincord.plugins.voice_logger.store import NAMESPACE, add_channels, read_settings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.storage import JSON, Store


def available(guild_id: int) -> FakeGuild:
    """Guild ``guild_id`` with the voice channel 30 and the category 20."""
    guild = FakeGuild(guild_id, f"guild {guild_id}")
    guild.channels = [
        FakeVoiceChannel(id=30, name="Room A", guild=guild, category_id=20),
        FakeChannel(id=20, name="Voice", type=discord.ChannelType.category),
    ]
    return guild


async def listed(store: Store, guild_id: int) -> None:
    """Listen channel 5 allows 30 and the deleted 31 and blocks the deleted category 21; listen
    channel 6 allows the category 20."""
    await add_channels(store, guild_id, 5, "allow", [30, 31])
    await add_channels(store, guild_id, 5, "block", [21])
    await add_channels(store, guild_id, 6, "allow", [20])


async def test_deleted_channels(
    bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    await listed(store, 10)
    monkeypatch.setattr(bot, "get_guild", {10: available(10)}.get)

    with caplog.at_level(logging.INFO):
        await dispatch(bot, "ready")

    assert await read_settings(store, 10) == {
        5: Setting(allow=(30,)),
        6: Setting(allow=(20,)),
    }
    assert (
        "VoiceLogger dropped the deleted channels 31, 21 from the lists of guild 10 (10)"
        in caplog.text
    )


async def test_nothing_deleted(bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    await add_channels(store, 10, 5, "allow", [30, 20])
    # An entry as a hand edit left it: a check that removes nothing rewrites nothing.
    document = await store.get(NAMESPACE, "10")
    assert isinstance(document, dict)
    edited: dict[str, JSON] = {
        **document,
        "6": {"allow_mode": True, "allow": [], "block": [], "x": 1},
    }
    await store.put(NAMESPACE, "10", edited)
    monkeypatch.setattr(bot, "get_guild", {10: available(10)}.get)

    await dispatch(bot, "ready")

    assert await store.get(NAMESPACE, "10") == edited


async def test_unavailable_or_unreadable(
    bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    await listed(store, 10)
    await store.put(NAMESPACE, "20", [])  # not v3's document
    await listed(store, 30)
    guilds = {10: FakeGuild(10, unavailable=True), 20: available(20), 30: available(30)}
    monkeypatch.setattr(bot, "get_guild", guilds.get)

    await dispatch(bot, "ready")

    # An unavailable guild (an outage) has no channels in discord.py's cache.
    assert (await read_settings(store, 10))[5] == Setting(allow=(30, 31), block=(21,))
    assert await store.get(NAMESPACE, "20") == []
    assert "VoiceLogger cannot check the settings of guild 20" in caplog.text
    assert (await read_settings(store, 30))[5] == Setting(allow=(30,))


async def ready_bot(store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Bot:
    """Load the plugin into a bot that is ready and knows the available guild 10."""
    guilds = {10: available(10)}

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return guilds.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)
    return await load_plugin("VoiceLogger", tmp_path / "plugins", store)


async def test_loaded_into_a_ready_bot(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    await listed(store, 10)

    bot = await ready_bot(store, tmp_path, monkeypatch)

    assert bot.loaded == ("VoiceLogger",)
    assert (await read_settings(store, 10))[5] == Setting(allow=(30,))


async def test_a_key_that_is_not_a_guild_id(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Settings are checked when the bot is ready."""
    # A hand edit or a faulty migration; the plugin never writes such a key.
    document: dict[str, JSON] = {"5": {"allow_mode": True, "allow": [31], "block": []}}
    await store.put(NAMESPACE, "general", document)
    await listed(store, 10)

    bot = await ready_bot(store, tmp_path, monkeypatch)
    await dispatch(bot, "ready")

    assert bot.loaded == ("VoiceLogger",)
    warning = "VoiceLogger ignores the settings stored under 'general', which is not a guild ID"
    assert caplog.text.count(warning) == 2  # at the load and at READY
    assert (await read_settings(store, 10))[5] == Setting(allow=(30,))
    assert await store.get(NAMESPACE, "general") == document
