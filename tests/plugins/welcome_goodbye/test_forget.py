"""A guild's channels are deleted when the bot leaves it, also while the bot was offline.

Kotlin (v3 deleted them only on a GuildLeaveEvent received while the plugin was enabled):
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:55-57
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/Event.kt:77-80
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:38-40
"""

import logging
from typing import TYPE_CHECKING

from discord_fakes import FakeGuild
from plugin_fakes import dispatch, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.welcome_goodbye.store import NAMESPACE, set_channel

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.storage import Store

# Guild 10 is available and guild 20 unavailable (an outage); the bot left guild 30.
GUILDS = {10: FakeGuild(10), 20: FakeGuild(20, unavailable=True)}


async def bind_three(store: Store) -> None:
    """Store channels for the guilds 10, 20 and 30."""
    await set_channel(store, 10, "welcome", 1)
    await set_channel(store, 20, "bye", 2)
    await set_channel(store, 30, "welcome", 3)


async def test_bot_leaves(bot: Bot, store: Store) -> None:
    """Requirement: Channels are forgotten with the guild."""
    await bind_three(store)

    await dispatch(bot, "guild_remove", FakeGuild(10).as_guild())

    assert await store.keys(NAMESPACE) == ["20", "30"]


async def test_left_while_offline(
    bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Channels are forgotten with the guild."""
    await bind_three(store)
    monkeypatch.setattr(bot, "get_guild", GUILDS.get)

    with caplog.at_level(logging.INFO):
        await dispatch(bot, "ready")

    assert await store.keys(NAMESPACE) == ["10", "20"]
    assert "WelcomeGoodbye deleted the channels of guild 30, which the bot left" in caplog.text


async def test_loaded_into_a_ready_bot(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Channels are forgotten with the guild."""
    await bind_three(store)

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return GUILDS.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)

    bot = await load_plugin("WelcomeGoodbye", tmp_path / "plugins", store)

    assert bot.loaded == ("WelcomeGoodbye",)
    assert await store.keys(NAMESPACE) == ["10", "20"]
