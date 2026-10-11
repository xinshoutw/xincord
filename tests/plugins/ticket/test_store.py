"""Each guild's panels in the store, one document per guild."""

import json
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import golden
from xincord.plugins.ticket.model import DataError, Entry
from xincord.plugins.ticket.store import NAMESPACE, Panels

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store
    from xincord.plugins.ticket.store import Undo

GOLDEN = golden("ticket")
GUILD = 10
PANEL = "1290000000000000001"  # the panel of the example document


async def keep(store: Store, document: JSON, guild: int = GUILD) -> None:
    """Store a guild's document."""
    await store.put(NAMESPACE, str(guild), document)


async def test_document(store: Store) -> None:
    """Requirement: Panels are stored as documents."""
    await keep(store, json.loads(GOLDEN["document"]))
    panels = Panels(store)

    first = await panels.entry(GUILD, PANEL, "0")
    second = await panels.entry(GUILD, PANEL, "1")

    assert first is not None
    assert first.admin_ids == (1280000000000000002,)
    assert first.category_id == 0
    assert second == Entry(GOLDEN["refund"], (), 1270000000000000003)


@pytest.mark.parametrize(
    ("message", "index"),
    [("1", "0"), (PANEL, "2"), (PANEL, "-1"), (PANEL, "x"), (PANEL, "")],
)
async def test_missing_entries(store: Store, message: str, index: str) -> None:
    """Requirement: Panels are stored as documents."""
    await keep(store, json.loads(GOLDEN["document"]))
    before = await store.get(NAMESPACE, str(GUILD))
    panels = Panels(store)

    assert await panels.entry(GUILD, message, index) is None
    assert await panels.entry(11, PANEL, "0") is None
    # Reading writes nothing.
    assert await store.get(NAMESPACE, "11") is None
    assert await store.get(NAMESPACE, str(GUILD)) == before


async def test_appending_keeps_the_others(store: Store) -> None:
    """Requirement: Panels are stored as documents."""
    kept: JSON = {"reasonTitle": "a", "adminIds": [], "categoryId": 0, "extra": 1}
    await keep(store, {"1": [kept], "2": []})

    index = await Panels(store).add(GUILD, "1", Entry("b", (3, 4), 30))

    document = await store.get(NAMESPACE, str(GUILD))
    assert index == 1
    assert document == {
        "1": [kept, {"reasonTitle": "b", "adminIds": [3, 4], "categoryId": 30}],
        "2": [],
    }
    assert isinstance(document, dict)
    added = document["1"]
    assert isinstance(added, list)
    assert isinstance(added[1], dict)
    assert list(added[1]) == ["reasonTitle", "adminIds", "categoryId"]  # the stored order


async def test_placed_before_stored(store: Store) -> None:
    """Requirement: Panels are stored as documents."""
    panels = Panels(store)
    placed: list[int] = []

    async def place(index: int) -> Undo:
        placed.append(index)

        async def undo() -> None:  # runs only when the store fails
            placed.remove(index)

        return undo

    async def refuse(index: int) -> Undo:
        raise RuntimeError(index)

    assert await panels.add(GUILD, "5", Entry("r", (), 0), place) == 0
    with pytest.raises(RuntimeError, match="1"):
        await panels.add(GUILD, "5", Entry("s", (), 0), refuse)

    assert placed == [0]
    assert await store.get(NAMESPACE, str(GUILD)) == {
        "5": [{"reasonTitle": "r", "adminIds": [], "categoryId": 0}]
    }


@pytest.mark.parametrize(
    "entry",
    [
        {"reasonTitle": "a", "adminIds": []},
        {"reasonTitle": "a", "adminIds": ["3"], "categoryId": 0},
        {"reasonTitle": "a", "adminIds": [True], "categoryId": 0},
        {"reasonTitle": 1, "adminIds": [], "categoryId": 0},
        {"reasonTitle": "a", "adminIds": [], "categoryId": False},
        {"reasonTitle": "a", "adminIds": [], "categoryId": 1.5},
        {"reasonTitle": "a", "adminIds": None, "categoryId": 0},
        "text",
    ],
)
async def test_broken_entries(store: Store, entry: JSON) -> None:
    """Requirement: Panels are stored as documents."""
    await keep(store, {PANEL: [entry]})

    with pytest.raises(DataError, match=f"guild {GUILD}, message {PANEL}"):
        await Panels(store).entry(GUILD, PANEL, "0")

    assert await store.get(NAMESPACE, str(GUILD)) == {PANEL: [entry]}


@pytest.mark.parametrize("document", [[], "x", {PANEL: "x"}, {PANEL: {}}])
async def test_broken_documents(store: Store, document: JSON) -> None:
    """Requirement: Panels are stored as documents."""
    await keep(store, document)
    panels = Panels(store)

    with pytest.raises(DataError, match=f"guild {GUILD}"):
        await panels.entry(GUILD, PANEL, "0")
    with pytest.raises(DataError, match=f"guild {GUILD}"):
        await panels.add(GUILD, PANEL, Entry("a", (), 0))

    assert await store.get(NAMESPACE, str(GUILD)) == document


async def test_forgotten_guilds(store: Store) -> None:
    """Requirement: Panels are stored as documents."""
    await keep(store, {"1": []})
    await keep(store, {"2": []}, guild=11)
    panels = Panels(store)

    assert sorted(await panels.guild_ids()) == ["10", "11"]
    await panels.forget(GUILD)

    assert await panels.guild_ids() == ["11"]
