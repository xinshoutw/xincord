"""Each guild's bindings and rooms in the store.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/JsonManager.kt:30-142
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/json/JsonData.kt:3-29
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from xincord.plugins.dynamic_voice_channel.store import (
    NAMESPACE,
    ROOMS,
    Binding,
    DataError,
    bind,
    drop,
    find,
    read_bindings,
    read_rooms,
    track,
    unbind,
    untrack,
)

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store

LOBBY = Binding(20, "Lobby", "A", "B")
TRACKED = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Rooms are tracked per guild"
)


async def test_first_binding(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    await bind(store, 10, LOBBY)

    document = await store.get(NAMESPACE, "10")
    assert document == [
        {"categoryId": 20, "defaultName": "Lobby", "formatName1": "A", "formatName2": "B"}
    ]
    assert isinstance(document, list)
    first = document[0]
    assert isinstance(first, dict)
    assert list(first) == ["categoryId", "defaultName", "formatName1", "formatName2"]  # Moshi's
    assert await read_bindings(store, 10) == [LOBBY]


async def test_guild_without_bindings(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    assert await read_bindings(store, 10) == []
    assert await store.keys(NAMESPACE) == []


async def test_missing_formats(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    # Moshi's defaults for formatName1 and formatName2; unknown fields are ignored.
    await store.put(NAMESPACE, "10", [{"categoryId": 20, "defaultName": "Lobby", "x": 1}])

    assert await read_bindings(store, 10) == [Binding(20, "Lobby", "", "")]


def test_find() -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    first, other, second = (
        Binding(20, "Lobby", "A"),
        Binding(21, "Lobby"),
        Binding(20, "Lobby", "B"),
    )
    bindings = [other, first, second]

    assert find(bindings, 20, "Lobby") is first  # v3's set kept the first of duplicates
    assert find(bindings, 21, "Lobby") is other
    assert find(bindings, 20, "lobby") is None  # names match exactly, case included
    assert find(bindings, 22, "Lobby") is None
    assert find([], 20, "Lobby") is None


async def test_binding_again(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    # v3's bind appended a second entry instead of replacing the first.
    other: dict[str, JSON] = {"categoryId": 21, "defaultName": "Other", "note": "kept"}
    await store.put(
        NAMESPACE,
        "10",
        [
            {"categoryId": 20, "defaultName": "Lobby", "formatName1": "A", "formatName2": "x"},
            other,
            {"categoryId": 20, "defaultName": "Lobby", "formatName1": "B", "formatName2": "y"},
        ],
    )
    found = find(await read_bindings(store, 10), 20, "Lobby")
    assert found == Binding(20, "Lobby", "A", "x")

    await bind(store, 10, Binding(20, "Lobby", "C", "z"))

    assert await store.get(NAMESPACE, "10") == [
        other,
        {"categoryId": 20, "defaultName": "Lobby", "formatName1": "C", "formatName2": "z"},
    ]


async def test_unbinding(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    await bind(store, 10, LOBBY)

    assert await unbind(store, 10, 20, "Lobby")
    assert await store.keys(NAMESPACE) == []  # the last binding takes the document with it
    assert not await unbind(store, 10, 20, "Lobby")
    assert await store.keys(NAMESPACE) == []  # nothing written for a binding that is not there


async def test_unbinding_duplicates(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    await store.put(
        NAMESPACE,
        "10",
        [
            {"categoryId": 20, "defaultName": "Lobby"},
            {"categoryId": 21, "defaultName": "Lobby"},
            {"categoryId": 20, "defaultName": "Lobby"},
        ],
    )

    assert not await unbind(store, 10, 20, "lobby")
    assert await unbind(store, 10, 20, "Lobby")
    assert await store.get(NAMESPACE, "10") == [{"categoryId": 21, "defaultName": "Lobby"}]


async def test_dropping_bindings(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    for binding in (Binding(20, "A"), Binding(21, "B"), Binding(22, "C")):
        await bind(store, 10, binding)

    await drop(store, 10, {(20, "A"), (22, "C"), (23, "D")})
    assert await read_bindings(store, 10) == [Binding(21, "B")]
    await drop(store, 10, {(21, "B")})
    assert await store.keys(NAMESPACE) == []
    await drop(store, 10, {(21, "B")})
    assert await store.keys(NAMESPACE) == []


async def test_concurrent_binds(store: Store) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    lobbies = [Binding(20, f"Lobby {number}") for number in range(20)]

    await asyncio.gather(*(bind(store, 10, lobby) for lobby in lobbies))

    assert sorted(await read_bindings(store, 10), key=lambda found: found.default_name) == sorted(
        lobbies, key=lambda lobby: lobby.default_name
    )


@pytest.mark.parametrize(
    "document",
    [
        {"categoryId": 20, "defaultName": "Lobby"},  # not a list
        ["Lobby"],
        [{"defaultName": "Lobby"}],
        [{"categoryId": "20", "defaultName": "Lobby"}],
        [{"categoryId": True, "defaultName": "Lobby"}],
        [{"categoryId": 20.0, "defaultName": "Lobby"}],
        [{"categoryId": 20}],
        [{"categoryId": 20, "defaultName": 5}],
        [{"categoryId": 20, "defaultName": "Lobby", "formatName1": None}],
        [{"categoryId": 20, "defaultName": "Lobby", "formatName2": 2}],
    ],
)
async def test_unreadable_entry(store: Store, document: JSON) -> None:
    """Requirement: Bindings are kept per guild in v3's documents."""
    await store.put(NAMESPACE, "10", document)

    with pytest.raises(DataError, match="guild 10"):
        await read_bindings(store, 10)
    with pytest.raises(DataError, match="guild 10"):
        await bind(store, 10, LOBBY)
    with pytest.raises(DataError, match="guild 10"):
        await unbind(store, 10, 20, "Lobby")
    with pytest.raises(DataError, match="guild 10"):
        await drop(store, 10, {(20, "Lobby")})
    assert await store.get(NAMESPACE, "10") == document


@TRACKED
async def test_tracked_rooms(store: Store) -> None:
    """Requirement: Rooms are tracked per guild."""
    await track(store, 10, 30, 1)
    await track(store, 10, 31, 2)

    assert await store.get(ROOMS, "10") == {"30": 1, "31": 2}
    assert await read_rooms(store, 10) == {30: 1, 31: 2}


@TRACKED
async def test_guild_without_rooms(store: Store) -> None:
    """Requirement: Rooms are tracked per guild."""
    assert await read_rooms(store, 10) == {}
    assert await store.keys(ROOMS) == []


@TRACKED
async def test_forgotten_rooms(store: Store) -> None:
    """Requirement: Rooms are tracked per guild."""
    await track(store, 10, 30, 1)
    await track(store, 10, 31, 2)

    await untrack(store, 10, 30)
    assert await store.get(ROOMS, "10") == {"31": 2}
    await untrack(store, 10, 31)
    assert await store.keys(ROOMS) == []  # the last room takes the document with it
    await untrack(store, 10, 32)
    assert await store.keys(ROOMS) == []  # nothing written for a room that is not tracked


@TRACKED
async def test_concurrent_tracks(store: Store) -> None:
    """Requirement: Rooms are tracked per guild."""
    rooms = range(30, 50)

    await asyncio.gather(*(track(store, 10, room, room + 100) for room in rooms))

    assert await read_rooms(store, 10) == {room: room + 100 for room in rooms}


@TRACKED
@pytest.mark.parametrize(
    "document",
    [[30], {"30": "1"}, {"30": True}, {"30": None}, {"room": 1}, {"030": 1}, {"-30": 1}],
)
async def test_unreadable_rooms(store: Store, document: JSON) -> None:
    """Requirement: Rooms are tracked per guild."""
    await store.put(ROOMS, "10", document)

    with pytest.raises(DataError, match="guild 10"):
        await read_rooms(store, 10)
    with pytest.raises(DataError, match="guild 10"):
        await track(store, 10, 31, 2)
    with pytest.raises(DataError, match="guild 10"):
        await untrack(store, 10, 30)
    assert await store.get(ROOMS, "10") == document
