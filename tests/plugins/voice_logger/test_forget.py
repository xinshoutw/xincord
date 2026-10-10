"""A guild's settings are deleted when the bot leaves it, also while the bot was offline.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/JsonManager.kt:29-40
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

import logging
from typing import TYPE_CHECKING

from discord_fakes import FakeGuild
from plugin_fakes import dispatch, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.listen_channels.store import ListenSettings
from xincord.plugins.voice_logger.cog import NAMESPACE

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.storage import Store


def settings(store: Store) -> ListenSettings:
    """VoiceLogger's listen channel settings in ``store``."""
    return ListenSettings(store, NAMESPACE)


async def settle_three(store: Store) -> None:
    """Settings of listen channel 5 in each of the guilds 10, 20 and 30, without lists."""
    for guild_id in (10, 20, 30):
        await settings(store).toggle(guild_id, 5)


async def test_forget(store: Store) -> None:
    """Requirement: Settings are forgotten with the guild."""
    await settle_three(store)

    await settings(store).forget(10)

    assert await store.keys(NAMESPACE) == ["20", "30"]
    await settings(store).forget(10)  # nothing left to delete
    assert await store.keys(NAMESPACE) == ["20", "30"]


async def test_guild_ids(store: Store) -> None:
    """Requirement: Settings are forgotten with the guild."""
    for guild_id in (12, 9, 10):
        await settings(store).toggle(guild_id, 5)

    assert await settings(store).guild_ids() == [9, 10, 12]


async def test_the_bot_leaves(bot: Bot, store: Store) -> None:
    """Requirement: Settings are forgotten with the guild."""
    await settle_three(store)

    await dispatch(bot, "guild_remove", FakeGuild(10).as_guild())

    # v3 handled no leave: the file stayed until the next start.
    assert await store.keys(NAMESPACE) == ["20", "30"]


async def test_left_while_offline(
    bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Settings are forgotten with the guild."""
    # The bot left guild 20; guild 30 is unavailable (an outage) and keeps its settings.
    await settle_three(store)
    guilds = {10: FakeGuild(10), 30: FakeGuild(30, unavailable=True)}
    monkeypatch.setattr(bot, "get_guild", guilds.get)

    with caplog.at_level(logging.INFO):
        await dispatch(bot, "ready")

    assert await store.keys(NAMESPACE) == ["10", "30"]
    assert "VoiceLogger deleted the settings of guild 20, which the bot left" in caplog.text


async def test_loaded_into_a_ready_bot(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Settings are forgotten with the guild."""
    await settle_three(store)
    guilds = {10: FakeGuild(10), 30: FakeGuild(30)}

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return guilds.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)

    bot = await load_plugin("VoiceLogger", tmp_path / "plugins", store)

    assert bot.loaded == ("VoiceLogger",)
    assert await store.keys(NAMESPACE) == ["10", "30"]
