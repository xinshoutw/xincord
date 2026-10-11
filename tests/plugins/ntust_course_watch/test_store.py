"""The registrations: v3's document in the store, changed under its lock.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:15-30
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:58-76
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/mongodb/ICacheDb.kt:92-112
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from xincord.plugins.ntust_course_watch.store import (
    KEY,
    NAMESPACE,
    DataError,
    Registrations,
    parse_registrations,
)

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store

# v3's document as its MemoryCacheDb wrote it: a member listed twice (v3's /course-add allowed it),
# a course whose only channel v3's /course-remove dropped, and an empty member list.
V3_DOCUMENT: JSON = {
    "CE162A001": {"5": ["1", "2", "1"], "6": ["3"]},
    "CE162A002": {},
    "CE162A003": {"5": []},
}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
def test_v3_document() -> None:
    """Requirement: Registrations are kept as v3's document."""
    assert parse_registrations(V3_DOCUMENT) == {"CE162A001": {5: (1, 2), 6: (3,)}}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
async def test_load(store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    registrations = Registrations(store)
    assert await registrations.load() == {}  # no document: nothing registered, nothing written
    assert await store.get(NAMESPACE, KEY) is None

    await store.put(NAMESPACE, KEY, V3_DOCUMENT)

    assert await registrations.load() == {"CE162A001": {5: (1, 2), 6: (3,)}}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
async def test_written_as_v3(store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    registrations = Registrations(store)

    assert await registrations.add("CE162A001", 5, 1)
    assert await registrations.add("CE162A001", 5, 2)
    assert await registrations.add("CE162A002", 6, 1)

    assert await store.get(NAMESPACE, KEY) == {
        "CE162A001": {"5": ["1", "2"]},
        "CE162A002": {"6": ["1"]},
    }


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
async def test_add_twice(store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    await store.put(NAMESPACE, KEY, V3_DOCUMENT)
    registrations = Registrations(store)

    assert not await registrations.add("CE162A001", 5, 2)

    assert await store.get(NAMESPACE, KEY) == V3_DOCUMENT  # nothing written: v3's duplicate stays


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
async def test_remove(store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    await store.put(NAMESPACE, KEY, V3_DOCUMENT)
    registrations = Registrations(store)

    assert not await registrations.remove("CE162A001", 5, 4)  # not registered: nothing written
    assert await store.get(NAMESPACE, KEY) == V3_DOCUMENT
    assert await registrations.remove("CE162A001", 5, 1)  # both of v3's entries go

    assert await store.get(NAMESPACE, KEY) == {"CE162A001": {"5": ["2"], "6": ["3"]}}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
async def test_last_registration(store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    registrations = Registrations(store)
    await registrations.add("CE162A001", 5, 1)
    await registrations.add("CE162A001", 6, 1)

    assert await registrations.remove("CE162A001", 5, 1)
    assert await store.get(NAMESPACE, KEY) == {"CE162A001": {"6": ["1"]}}
    assert await registrations.remove("CE162A001", 6, 1)

    assert await store.get(NAMESPACE, KEY) is None
    assert await registrations.load() == {}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
async def test_forget_a_channel(store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    await store.put(NAMESPACE, KEY, V3_DOCUMENT)
    registrations = Registrations(store)

    assert not await registrations.forget(7)
    assert await store.get(NAMESPACE, KEY) == V3_DOCUMENT
    assert await registrations.forget(5)

    assert await store.get(NAMESPACE, KEY) == {"CE162A001": {"6": ["3"]}}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
@pytest.mark.parametrize(
    "document",
    [
        pytest.param([], id="a list"),
        pytest.param("x", id="text"),
        pytest.param({"CE162A001": []}, id="a course's channels in a list"),
        pytest.param({"CE162A001": {"general": ["1"]}}, id="a channel key that is not a number"),
        pytest.param({"CE162A001": {"-5": ["1"]}}, id="a negative channel"),
        pytest.param({"CE162A001": {"5": "1"}}, id="members as text"),
        pytest.param({"CE162A001": {"5": [1]}}, id="a member as a number"),
        pytest.param({"CE162A001": {"5": ["1a"]}}, id="a member that is not a number"),
    ],
)
async def test_broken_document(store: Store, document: JSON) -> None:
    """Requirement: Registrations are kept as v3's document."""
    await store.put(NAMESPACE, KEY, document)
    registrations = Registrations(store)

    with pytest.raises(DataError):
        await registrations.load()
    with pytest.raises(DataError):
        await registrations.add("CE162A001", 5, 1)
    with pytest.raises(DataError):
        await registrations.remove("CE162A001", 5, 1)
    with pytest.raises(DataError):
        await registrations.forget(5)

    assert await store.get(NAMESPACE, KEY) == document  # never overwritten


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Registrations are kept as v3's document"
)
async def test_concurrent_registrations(store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    registrations = Registrations(store)

    # discord.py runs the commands of two members as concurrent tasks.
    await asyncio.gather(
        *(registrations.add("CE162A001", 5, user) for user in range(1, 11)),
        registrations.add("CE162A002", 6, 1),
    )

    assert await registrations.load() == {
        "CE162A001": {5: tuple(range(1, 11))},
        "CE162A002": {6: (1,)},
    }
