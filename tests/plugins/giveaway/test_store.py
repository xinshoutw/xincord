"""Stored giveaways: v3's Moshi documents per guild, read and changed one entry at a time.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/data/GiveawayData.kt:7-65
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:49-54
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:411-415
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from plugin_fakes import golden
from xincord.plugins.giveaway.model import (
    DataError,
    Draft,
    Instance,
    Policy,
    Prize,
    Winners,
    instance_json,
    parse_instance,
)
from xincord.plugins.giveaway.store import NAMESPACE, Giveaways

if TYPE_CHECKING:
    from collections.abc import Callable

    from xincord.core.storage import JSON, Store

REASON = "Giveaways are stored as v3's documents"
GOLDEN = golden("giveaway")
GUILD = 900000000000000010  # above 2^53, as Discord's snowflakes are
RUNNING, DRAWN = "3f2a9c1b7e4d4a60", "0123456789ab4def"


def v3_document() -> dict[str, Any]:
    """The golden document, as the store holds it."""
    document: dict[str, Any] = json.loads(GOLDEN["document"])
    return document


def compact(document: object) -> str:
    """JSON as Moshi wrote it, without spaces."""
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def minimal(**fields: JSON) -> dict[str, JSON]:
    """An entry with only v3's required fields, and ``fields``."""
    entry: dict[str, JSON] = {
        "id": "a1",
        "guildId": GUILD,
        "channelId": 5,
        "messageId": 42,
        "creatorId": 7,
        "config": {},
    }
    return entry | fields


def joined(user_id: int) -> Callable[[Instance], tuple[str, Instance]]:
    """A transition that adds ``user_id`` to the participants."""

    def add(instance: Instance) -> tuple[str, Instance]:
        return "joined", replace(instance, participant_ids=(*instance.participant_ids, user_id))

    return add


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_v3_documents(store: Store) -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    await store.put(NAMESPACE, str(GUILD), v3_document())
    giveaways = Giveaways(store)

    running = await giveaways.get(GUILD, RUNNING)
    drawn = await giveaways.get(GUILD, DRAWN)

    assert running == Instance(
        id=RUNNING,
        guild_id=GUILD,
        channel_id=900000000000000005,
        message_id=900000000000000042,
        creator_id=900000000000000007,
        config=Draft(
            title="Nitro",
            description="desc",
            thumbnail_url="https://x/y.png",
            end_at=1767225600,
            policy=Policy.UNIQUE_ACROSS_PRIZES,
            prizes=(Prize("Nitro", 2), Prize("Sticker", 1)),
        ),
        created_at=1767000000,
        participant_ids=(111, 222, 333),
    )
    assert running is not None
    assert drawn is not None
    assert drawn.ended
    assert drawn.ended_at == 1767225660
    assert drawn.locale_tag == "en-US"
    assert drawn.winner_results == (Winners("Nitro", (222, 111)), Winners("Sticker", (333,)))
    assert await giveaways.ids(GUILD) == {RUNNING, DRAWN}
    # Written back, both are v3's JSON again, in Moshi's field order.
    document = {
        key: instance_json(instance) for key, instance in ((RUNNING, running), (DRAWN, drawn))
    }
    assert compact(document) == GOLDEN["document"]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_defaults() -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    instance = parse_instance(minimal(), "guild 10, giveaway a1")

    assert instance == Instance("a1", GUILD, 5, 42, 7, Draft())
    assert instance.locale_tag == "zh-TW"
    assert (instance.created_at, instance.ended_at, instance.ended) == (0, None, False)
    assert (instance.participant_ids, instance.winner_results) == ((), ())
    assert instance.config.policy is Policy.ALLOW_DUPLICATE
    # A prize's count and a result's winners have v3's defaults too.
    config: dict[str, JSON] = {"prizes": [{"name": "Nitro"}]}
    results: list[JSON] = [{"prizeName": "Nitro"}]
    full = parse_instance(minimal(config=config, winnerResults=results), "here")
    assert full.config.prizes == (Prize("Nitro", 1),)
    assert full.winner_results == (Winners("Nitro", ()),)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_participants_read_once() -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    instance = parse_instance(minimal(participantIds=[3, 1, 3, 2, 1]), "here")

    assert instance.participant_ids == (3, 1, 2)  # v3's set, in insertion order


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_unknown_fields_dropped() -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    instance = parse_instance(minimal(extra="x"), "here")

    assert "extra" not in instance_json(instance)  # Moshi dropped them when it saved


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize(
    "entry",
    [
        {key: value for key, value in minimal().items() if key != "creatorId"},
        minimal(config={"winnerDuplicatePolicy": "RANDOM"}),
        minimal(guildId="900000000000000010"),
        minimal(messageId=4.2),
        minimal(ended=1),
        minimal(creatorId=True),
        minimal(localeTag=None),
        minimal(config=None),
        minimal(participantIds=["111"]),
        minimal(config={"prizes": [{"winnerCount": 1}]}),
        minimal(winnerResults=[{"winnerIds": []}]),
        minimal(winnerResults={}),
        "text",
    ],
    ids=[
        "no-creator",
        "policy",
        "text-id",
        "fraction-id",
        "number-flag",
        "flag-id",
        "null",
        "null-config",
        "text-participant",
        "nameless-prize",
        "nameless-result",
        "results-object",
        "not-an-object",
    ],
)
def test_not_v3_shape(entry: JSON) -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    with pytest.raises(DataError, match="guild 10, giveaway a1"):
        parse_instance(entry, "guild 10, giveaway a1")


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_broken_entry_stays(store: Store) -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    broken = minimal(config={"winnerDuplicatePolicy": "RANDOM"})
    document = {"a1": broken, RUNNING: v3_document()[RUNNING]}
    await store.put(NAMESPACE, str(GUILD), document)
    giveaways = Giveaways(store)

    with pytest.raises(DataError, match=f"guild {GUILD}, giveaway a1"):
        await giveaways.get(GUILD, "a1")
    with pytest.raises(DataError):
        await giveaways.change(GUILD, "a1", joined(9))
    changed = await giveaways.change(GUILD, RUNNING, joined(9))

    assert changed is not None
    stored = await store.get(NAMESPACE, str(GUILD))
    assert isinstance(stored, dict)
    assert stored["a1"] == broken  # never overwritten
    running = stored[RUNNING]
    assert isinstance(running, dict)
    assert running["participantIds"] == [111, 222, 333, 9]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("document", [[], "x", 5])
async def test_broken_document(store: Store, document: JSON) -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    await store.put(NAMESPACE, str(GUILD), document)
    giveaways = Giveaways(store)

    with pytest.raises(DataError, match=f"guild {GUILD}"):
        await giveaways.ids(GUILD)
    with pytest.raises(DataError):
        await giveaways.add(Instance("a1", GUILD, 5, 42, 7, Draft()))
    assert await store.get(NAMESPACE, str(GUILD)) == document


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_reads_write_nothing(store: Store) -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    giveaways = Giveaways(store)

    assert await giveaways.get(GUILD, RUNNING) is None
    assert await giveaways.ids(GUILD) == frozenset()
    assert await giveaways.change(GUILD, RUNNING, joined(9)) is None
    assert await store.keys(NAMESPACE) == []


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_add(store: Store) -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    giveaways = Giveaways(store)
    first = Instance("a1", GUILD, 5, 42, 7, Draft(title="Nitro"), created_at=1767000000)
    second = Instance("b2", GUILD, 5, 43, 7, Draft(title="Sticker"))

    await giveaways.add(first)
    await giveaways.add(second)
    with pytest.raises(DataError, match="a1"):
        await giveaways.add(replace(second, id="a1"))

    assert await giveaways.get(GUILD, "a1") == first
    assert await giveaways.get(GUILD, "b2") == second
    assert await store.get(NAMESPACE, str(GUILD)) == {
        "a1": instance_json(first),
        "b2": instance_json(second),
    }


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_unchanged_writes_nothing(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Giveaways are stored as v3's documents."""
    await store.put(NAMESPACE, str(GUILD), v3_document())
    giveaways = Giveaways(store)
    put = AsyncMock(wraps=store.put)
    monkeypatch.setattr(store, "put", put)

    result = await giveaways.change(GUILD, RUNNING, lambda instance: ("same", instance))

    assert result is not None
    assert result[0] == "same"
    put.assert_not_awaited()
