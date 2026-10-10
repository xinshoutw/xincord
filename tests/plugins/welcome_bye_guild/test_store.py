"""Each guild's channels in the store, as v3's data/<guildId>.json documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:25-57
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-41
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonFileManager.kt:29-67
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from xincord.plugins.welcome_bye_guild.store import (
    NAMESPACE,
    Bindings,
    forget,
    guild_ids,
    read,
    set_channel,
)

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store


async def test_unknown_guild(store: Store) -> None:
    """Requirement: Each guild's channels are stored."""
    assert await read(store, 10) == Bindings(welcome=0, bye=0)
    assert await store.keys(NAMESPACE) == []


@pytest.mark.xfail(strict=True, reason="Each guild's channels are stored")
async def test_v3_document(store: Store) -> None:
    """Requirement: Each guild's channels are stored."""
    assert await set_channel(store, 10, "welcome", 5) == (Bindings(welcome=5), 0)

    expected = {"10": {"welcomeChannelId": 5, "byeChannelId": 0}}
    assert await store.items("WelcomeGoodbye") == expected
    assert await read(store, 10) == Bindings(welcome=5)


async def test_snowflakes_stay_exact(store: Store) -> None:
    """Requirement: Each guild's channels are stored."""
    channel_id = 1277193832378667040  # more digits than a double holds exactly

    await set_channel(store, 1, "bye", channel_id)

    assert await read(store, 1) == Bindings(bye=channel_id)


async def test_missing_field(store: Store) -> None:
    """Requirement: Each guild's channels are stored."""
    await store.put(NAMESPACE, "10", {"welcomeChannelId": 5})
    await store.put(NAMESPACE, "20", {"byeChannelId": 6, "unknown": "kept out"})

    assert await read(store, 10) == Bindings(welcome=5)
    assert await read(store, 20) == Bindings(bye=6)


async def test_unchanged_channel(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Each guild's channels are stored."""
    assert await set_channel(store, 10, "welcome", 0) == (Bindings(), 0)
    assert await store.keys(NAMESPACE) == []

    await set_channel(store, 10, "welcome", 5)
    writes: list[tuple[str, str, JSON]] = []

    async def put(namespace: str, key: str, value: JSON) -> None:
        writes.append((namespace, key, value))

    monkeypatch.setattr(store, "put", put)

    assert await set_channel(store, 10, "welcome", 5) == (Bindings(welcome=5), 5)
    assert writes == []


async def test_concurrent_changes(store: Store) -> None:
    """Requirement: Each guild's channels are stored."""
    await asyncio.gather(set_channel(store, 10, "welcome", 5), set_channel(store, 10, "bye", 6))

    assert await read(store, 10) == Bindings(welcome=5, bye=6)


async def test_forgetting_a_guild(store: Store) -> None:
    """Requirement: Each guild's channels are stored."""
    await set_channel(store, 10, "welcome", 5)
    await set_channel(store, 20, "bye", 6)

    await forget(store, 10)

    assert await guild_ids(store) == [20]
    assert await read(store, 10) == Bindings()
    assert await read(store, 20) == Bindings(bye=6)
