"""Each guild's listen channel settings in the store, in v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/JsonManager.kt:17-117
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/json/JsonData.kt:5-15
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/ChannelData.kt:8-71
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:51-57
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from xincord.plugins.listen_channels.settings import Setting
from xincord.plugins.listen_channels.store import DataError, ListenSettings
from xincord.plugins.voice_logger.cog import NAMESPACE

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.storage import JSON, Store


def settings(store: Store) -> ListenSettings:
    """VoiceLogger's listen channel settings in ``store``."""
    return ListenSettings(store, NAMESPACE)


def writes(store: Store, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the store's writes from now on, which still happen."""
    recorded: list[str] = []
    put, delete = store.put, store.delete

    async def recording_put(namespace: str, key: str, value: JSON) -> None:
        recorded.append(f"put {namespace} {key}")
        await put(namespace, key, value)

    async def recording_delete(namespace: str, key: str) -> bool:
        recorded.append(f"delete {namespace} {key}")
        return await delete(namespace, key)

    monkeypatch.setattr(store, "put", recording_put)
    monkeypatch.setattr(store, "delete", recording_delete)
    return recorded


async def test_first_selection(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    setting = await settings(store).add_channels(10, 5, "allow", [30, 40])

    # v3 saved a first selection with allow_mode false while its menu showed the allow mode.
    assert setting == Setting(allow_mode=True, allow=(30, 40), block=())
    document = await store.get(NAMESPACE, "10")
    assert document == {"5": {"allow_mode": True, "allow": [30, 40], "block": []}}
    assert isinstance(document, dict)
    entry = document["5"]
    assert isinstance(entry, dict)
    assert list(entry) == ["allow_mode", "allow", "block"]  # Moshi's field order
    assert await settings(store).read_setting(10, 5) == setting


async def test_listen_channel_without_settings(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    assert await settings(store).read_setting(10, 5) == Setting(allow_mode=True, allow=(), block=())
    assert await settings(store).read_settings(10) == {}
    assert await store.keys(NAMESPACE) == []


async def test_toggling_and_adding(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    # v3's lists were sets: a duplicate reads once. Moshi ignored unknown fields.
    other: dict[str, JSON] = {"allow_mode": False, "allow": [], "block": [31], "note": "kept"}
    await store.put(
        NAMESPACE, "10", {"5": {"allow_mode": True, "allow": [30, 40, 30], "block": []}, "6": other}
    )

    assert (await settings(store).toggle(10, 5)).allow_mode is False
    assert (await settings(store).toggle(10, 5)).allow_mode is True
    assert await settings(store).add_channels(10, 5, "allow", [40, 50]) == Setting(
        allow=(30, 40, 50)
    )
    assert await settings(store).add_channels(10, 5, "block", [60]) == Setting(
        allow=(30, 40, 50), block=(60,)
    )

    assert await store.get(NAMESPACE, "10") == {
        "5": {"allow_mode": True, "allow": [30, 40, 50], "block": [60]},
        "6": other,  # entries that a change does not touch stay as they were
    }
    assert await settings(store).read_settings(10) == {
        5: Setting(allow=(30, 40, 50), block=(60,)),
        6: Setting(allow_mode=False, block=(31,)),
    }


async def test_toggling_a_channel_without_settings(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    assert await settings(store).toggle(10, 5) == Setting(allow_mode=False)

    assert await store.get(NAMESPACE, "10") == {
        "5": {"allow_mode": False, "allow": [], "block": []}
    }


async def test_nothing_to_change(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    await settings(store).add_channels(10, 5, "allow", [30, 40])
    written = writes(store, monkeypatch)

    assert await settings(store).add_channels(10, 5, "allow", [40, 30]) == Setting(allow=(30, 40))
    assert not await settings(store).remove(10, 6)  # no entry
    assert not await settings(store).remove(11, 5)  # no document

    assert written == []


async def test_removing(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    await settings(store).add_channels(10, 5, "allow", [30])
    await settings(store).add_channels(10, 6, "block", [31])

    assert await settings(store).remove(10, 5)
    assert await store.get(NAMESPACE, "10") == {
        "6": {"allow_mode": True, "allow": [], "block": [31]}
    }
    assert await settings(store).remove(10, 6)
    assert await store.keys(NAMESPACE) == []  # the last entry takes the document with it


async def test_concurrent_changes(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    await asyncio.gather(
        *(settings(store).add_channels(10, channel, "allow", [30]) for channel in range(1, 21))
    )

    assert sorted(await settings(store).read_settings(10)) == list(range(1, 21))


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"5": {"allow_mode": True, "allow": []}},  # Moshi required every field
        {"5": {"allow_mode": True, "allow": ["30"], "block": []}},
        {"5": {"allow_mode": True, "allow": [True], "block": []}},
        {"5": {"allow_mode": 1, "allow": [], "block": []}},
        {"5": []},
        {"general": {"allow_mode": True, "allow": [], "block": []}},
        {"05": {"allow_mode": True, "allow": [], "block": []}},
    ],
)
async def test_unreadable_settings(store: Store, document: JSON) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    await store.put(NAMESPACE, "10", document)
    calls: list[Callable[[], Awaitable[object]]] = [
        lambda: settings(store).read_settings(10),
        lambda: settings(store).read_setting(10, 5),
        lambda: settings(store).toggle(10, 5),
        lambda: settings(store).add_channels(10, 5, "block", [31]),
        lambda: settings(store).remove(10, 5),
    ]

    for call in calls:
        with pytest.raises(DataError, match="guild 10"):
            await call()

    assert await store.get(NAMESPACE, "10") == document
