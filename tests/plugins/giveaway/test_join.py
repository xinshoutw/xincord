"""Joining and leaving: Join / Leave toggles the user among the participants of a running giveaway.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:246-279
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:388-428
"""

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import embed_dict
from plugin_fakes import golden
from xincord.plugins.giveaway.model import Draft, Instance, Prize

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")
REASON = "Members join and leave"
NOW = 1772244000  # the tests' clock
GIVEAWAY = Instance(
    id="3f2a9c1b7e4d4a60",
    guild_id=10,
    channel_id=5,
    message_id=500,
    creator_id=7,
    config=Draft(title="Nitro", end_at=NOW + 3600, prizes=(Prize("Nitro", 1),)),
    locale_tag="en-US",
)


def participants(fields: dict[str, Any]) -> str:
    """The participant count that a replaced post shows."""
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    value: str = embed_dict(embed)["fields"][1]["value"]
    return value


def updated(interaction: FakeInteraction) -> tuple[str, str]:
    """The post's participant count in the press's response, and the ephemeral follow-up."""
    (method, post), (followup, reply) = interaction.sent
    assert method == "response.edit_message"
    assert isinstance(post["view"], discord.ui.View)
    assert followup == "followup.send"
    assert reply["ephemeral"] is True
    return participants(post), str(reply["content"])


def told(interaction: FakeInteraction) -> object:
    """The text of the interaction's only response, an ephemeral reply."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_message"
    assert fields["ephemeral"] is True
    return fields["content"]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_join_and_leave(scene: Scene, locale: str) -> None:
    """Requirement: Members join and leave."""
    await scene.add(replace(GIVEAWAY, locale_tag=locale))
    replies = GOLDEN["replies"][locale]

    joined = await scene.click("participate", GIVEAWAY.id)
    assert (await scene.stored(GIVEAWAY.id)).participant_ids == (8,)
    left = await scene.click("participate", GIVEAWAY.id)

    assert (await scene.stored(GIVEAWAY.id)).participant_ids == ()
    assert updated(joined) == ("1", replies["joined"])
    assert updated(left) == ("0", replies["left"])


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize(
    "giveaway",
    [
        replace(GIVEAWAY, ended=True, ended_at=NOW - 60),
        replace(GIVEAWAY, config=replace(GIVEAWAY.config, end_at=NOW)),  # the end time has come
    ],
    ids=["drawn", "ended"],
)
async def test_closed(scene: Scene, giveaway: Instance) -> None:
    """Requirement: Members join and leave."""
    await scene.add(replace(giveaway, locale_tag="zh-TW"))

    clicked = await scene.click("participate", GIVEAWAY.id)  # an en-US member

    assert told(clicked) == GOLDEN["replies"]["zh-TW"]["closed"]  # the giveaway's language
    assert (await scene.stored(GIVEAWAY.id)).participant_ids == ()


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_another_message(scene: Scene) -> None:
    """Requirement: Members join and leave."""
    await scene.add(GIVEAWAY)

    clicked = await scene.click(
        "participate", GIVEAWAY.id, scene.who(user=8, admin=False, message_id=999)
    )

    assert clicked.sent == [("response.defer", {"ephemeral": False, "thinking": False})]
    assert (await scene.stored(GIVEAWAY.id)).participant_ids == ()


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_unknown_giveaway(scene: Scene, locale: str) -> None:
    """Requirement: Members join and leave."""
    clicked = await scene.click(
        "participate", "0000000000000000", scene.who(user=8, locale=locale, message_id=500)
    )

    assert told(clicked) == GOLDEN["replies"][locale]["not-found"]  # the member's language
    assert await scene.store.keys("Giveaway") == []


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_joins_at_once(scene: Scene) -> None:
    """Requirement: Members join and leave."""
    await scene.add(GIVEAWAY)

    await asyncio.gather(
        scene.click("participate", GIVEAWAY.id, scene.who(user=8, message_id=500)),
        scene.click("participate", GIVEAWAY.id, scene.who(user=9, message_id=500)),
        scene.click("participate", GIVEAWAY.id, scene.who(user=10, message_id=500)),
    )

    assert sorted((await scene.stored(GIVEAWAY.id)).participant_ids) == [8, 9, 10]
