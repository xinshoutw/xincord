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

from xincord.plugins.voice_logger.settings import Setting
from xincord.plugins.voice_logger.store import (
    NAMESPACE,
    DataError,
    add_channels,
    read_setting,
    read_settings,
    remove,
    toggle,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.storage import JSON, Store

XFAIL = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Settings are kept per guild in v3's documents",
)


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


@XFAIL
async def test_first_selection(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    setting = await add_channels(store, 10, 5, "allow", [30, 40])

    # v3 saved a first selection with allow_mode false while its menu showed the allow mode.
    assert setting == Setting(allow_mode=True, allow=(30, 40), block=())
    document = await store.get(NAMESPACE, "10")
    assert document == {"5": {"allow_mode": True, "allow": [30, 40], "block": []}}
    assert isinstance(document, dict)
    entry = document["5"]
    assert isinstance(entry, dict)
    assert list(entry) == ["allow_mode", "allow", "block"]  # Moshi's field order
    assert await read_setting(store, 10, 5) == setting


@XFAIL
async def test_listen_channel_without_settings(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    assert await read_setting(store, 10, 5) == Setting(allow_mode=True, allow=(), block=())
    assert await read_settings(store, 10) == {}
    assert await store.keys(NAMESPACE) == []


@XFAIL
async def test_toggling_and_adding(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    # v3's lists were sets: a duplicate reads once. Moshi ignored unknown fields.
    other: dict[str, JSON] = {"allow_mode": False, "allow": [], "block": [31], "note": "kept"}
    await store.put(
        NAMESPACE, "10", {"5": {"allow_mode": True, "allow": [30, 40, 30], "block": []}, "6": other}
    )

    assert (await toggle(store, 10, 5)).allow_mode is False
    assert (await toggle(store, 10, 5)).allow_mode is True
    assert await add_channels(store, 10, 5, "allow", [40, 50]) == Setting(allow=(30, 40, 50))
    assert await add_channels(store, 10, 5, "block", [60]) == Setting(
        allow=(30, 40, 50), block=(60,)
    )

    assert await store.get(NAMESPACE, "10") == {
        "5": {"allow_mode": True, "allow": [30, 40, 50], "block": [60]},
        "6": other,  # entries that a change does not touch stay as they were
    }
    assert await read_settings(store, 10) == {
        5: Setting(allow=(30, 40, 50), block=(60,)),
        6: Setting(allow_mode=False, block=(31,)),
    }


@XFAIL
async def test_toggling_a_channel_without_settings(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    assert await toggle(store, 10, 5) == Setting(allow_mode=False)

    assert await store.get(NAMESPACE, "10") == {
        "5": {"allow_mode": False, "allow": [], "block": []}
    }


@XFAIL
async def test_nothing_to_change(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    await add_channels(store, 10, 5, "allow", [30, 40])
    written = writes(store, monkeypatch)

    assert await add_channels(store, 10, 5, "allow", [40, 30]) == Setting(allow=(30, 40))
    assert not await remove(store, 10, 6)  # no entry
    assert not await remove(store, 11, 5)  # no document

    assert written == []


@XFAIL
async def test_removing(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    await add_channels(store, 10, 5, "allow", [30])
    await add_channels(store, 10, 6, "block", [31])

    assert await remove(store, 10, 5)
    assert await store.get(NAMESPACE, "10") == {
        "6": {"allow_mode": True, "allow": [], "block": [31]}
    }
    assert await remove(store, 10, 6)
    assert await store.keys(NAMESPACE) == []  # the last entry takes the document with it


@XFAIL
async def test_concurrent_changes(store: Store) -> None:
    """Requirement: Settings are kept per guild in v3's documents."""
    await asyncio.gather(
        *(add_channels(store, 10, channel, "allow", [30]) for channel in range(1, 21))
    )

    assert sorted(await read_settings(store, 10)) == list(range(1, 21))


@XFAIL
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
        lambda: read_settings(store, 10),
        lambda: read_setting(store, 10, 5),
        lambda: toggle(store, 10, 5),
        lambda: add_channels(store, 10, 5, "block", [31]),
        lambda: remove(store, 10, 5),
    ]

    for call in calls:
        with pytest.raises(DataError, match="guild 10"):
            await call()

    assert await store.get(NAMESPACE, "10") == document
