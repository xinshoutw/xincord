"""Each guild's wallets in the store, as v3's data/<guildId>.json documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/JsonImpl.kt:17-173
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/json/JsonData.kt:3-10
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonFileManager.kt:29-113
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from xincord.plugins.economy.store import NAMESPACE, DataError, change, read, read_all
from xincord.plugins.economy.wallet import OPERATIONS, Wallet

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store

ADD_MONEY = OPERATIONS["add-money"]


async def test_first_change(store: Store) -> None:
    """Requirement: Wallets are kept per guild in v3's documents."""
    assert await change(store, 10, 7, ADD_MONEY, 5) == (Wallet(), Wallet(money=5))

    assert await store.items(NAMESPACE) == {"10": {"7": {"cost": 0, "money": 5}}}
    document = await store.get(NAMESPACE, "10")
    assert isinstance(document, dict)
    entry = document["7"]
    assert isinstance(entry, dict)
    assert list(entry) == ["cost", "money"]  # Moshi's field order
    assert await read(store, 10, 7) == Wallet(money=5)


async def test_user_without_a_wallet(store: Store) -> None:
    """Requirement: Wallets are kept per guild in v3's documents."""
    await store.put(NAMESPACE, "10", {"7": {"cost": 1, "money": 2}})

    assert await read(store, 10, 8) == Wallet()
    assert await read(store, 20, 8) == Wallet()
    assert await read_all(store, 20) == {}
    assert await store.items(NAMESPACE) == {"10": {"7": {"cost": 1, "money": 2}}}


async def test_other_entries_kept(store: Store) -> None:
    """Requirement: Wallets are kept per guild in v3's documents."""
    await store.put(
        NAMESPACE,
        "10",
        {
            "7": {"money": 1, "cost": 2, "note": "not v3's"},
            "8": {"cost": 3, "money": 4},
            "data": {"anything": True},  # v3 kept keys that are not user IDs in the file
            "007": {"cost": 5, "money": 6},
        },
    )

    assert await change(store, 10, 7, OPERATIONS["add-cost"], 5) == (
        Wallet(money=1, cost=2),
        Wallet(money=1, cost=7),
    )
    assert await store.get(NAMESPACE, "10") == {
        "7": {"cost": 7, "money": 1},
        "8": {"cost": 3, "money": 4},
        "data": {"anything": True},
        "007": {"cost": 5, "money": 6},
    }
    assert await read_all(store, 10) == {7: Wallet(money=1, cost=7), 8: Wallet(money=4, cost=3)}


async def test_amounts_stay_exact(store: Store) -> None:
    """Requirement: Wallets are kept per guild in v3's documents."""
    await change(store, 10, 7, OPERATIONS["set-money"], 2**53 + 1)  # past a double's precision
    await change(store, 10, 7, ADD_MONEY, 2**53)

    assert await read(store, 10, 7) == Wallet(money=2**54 + 1)


@pytest.mark.parametrize(
    "entry",
    [
        {"cost": "7", "money": 1},
        {"cost": 1, "money": None},
        {"cost": 1},
        {"cost": True, "money": 1},
        {"cost": 1.5, "money": 1},
        None,
        [1, 2],
    ],
    ids=["quoted", "null-field", "missing", "boolean", "fraction", "null", "list"],
)
async def test_unreadable_entry(store: Store, entry: JSON) -> None:
    """Requirement: Wallets are kept per guild in v3's documents."""
    document: JSON = {"7": entry, "8": {"cost": 0, "money": 3}}
    await store.put(NAMESPACE, "10", document)

    with pytest.raises(DataError, match=r"guild 10.*user 7"):
        await read(store, 10, 7)
    with pytest.raises(DataError, match=r"guild 10.*user 7"):
        await change(store, 10, 7, ADD_MONEY, 1)
    with pytest.raises(DataError, match=r"guild 10.*user 7"):
        await read_all(store, 10)
    assert await store.get(NAMESPACE, "10") == document
    # The other users' wallets still work, and the unreadable entry stays as it was.
    assert await read(store, 10, 8) == Wallet(money=3)
    await change(store, 10, 8, ADD_MONEY, 1)
    assert await store.get(NAMESPACE, "10") == {"7": entry, "8": {"cost": 0, "money": 4}}


async def test_unreadable_document(store: Store) -> None:
    """Requirement: Wallets are kept per guild in v3's documents."""
    await store.put(NAMESPACE, "10", [1, 2])

    with pytest.raises(DataError, match=r"guild 10"):
        await read(store, 10, 7)
    with pytest.raises(DataError, match=r"guild 10"):
        await change(store, 10, 7, ADD_MONEY, 1)
    assert await store.get(NAMESPACE, "10") == [1, 2]


async def test_concurrent_changes(store: Store) -> None:
    """Requirement: Changes are atomic."""
    await asyncio.gather(*(change(store, 10, 7, ADD_MONEY, 1) for _ in range(50)))
    await asyncio.gather(*(change(store, 10, user, ADD_MONEY, 1) for user in range(1, 7)))

    assert await read(store, 10, 7) == Wallet(money=50)
    assert await read_all(store, 10) == {user: Wallet(money=1) for user in range(1, 7)} | {
        7: Wallet(money=50)
    }
