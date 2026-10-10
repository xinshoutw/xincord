"""Drawing: the creator or an administrator draws once the end time has come; admins reroll.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:281-386
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/resources/lang/en-US/message/draw-result.yaml:1
"""

import asyncio
import random
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import embed_dict
from plugin_fakes import golden
from xincord.plugins.giveaway.model import (
    Draft,
    Instance,
    Policy,
    Prize,
    Winners,
    draw_winners,
)

if TYPE_CHECKING:
    import discord

    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")
NOW = 1772244000  # the tests' clock
END = 1772330400  # a day later
GIVEAWAY = Instance(
    id="3f2a9c1b7e4d4a60",
    guild_id=10,
    channel_id=5,
    message_id=500,
    creator_id=7,
    config=Draft(
        title="Nitro",
        end_at=NOW - 60,  # ended a minute ago
        policy=Policy.UNIQUE_ACROSS_PRIZES,
        prizes=(Prize("Nitro", 2), Prize("Sticker", 1)),
    ),
    locale_tag="en-US",
    participant_ids=(111, 222, 333, 444),
)
DRAWN = replace(
    GIVEAWAY,
    ended=True,
    ended_at=NOW - 30,
    winner_results=(Winners("Nitro", (111, 222)), Winners("Sticker", (333,))),
)


def seeded(seed: int) -> random.Random:
    """A generator whose draws the test can repeat; the plugin draws with SystemRandom."""
    return random.Random(seed)  # noqa: S311 - reproducible draws, not secrets


def drawn(interaction: FakeInteraction) -> tuple[dict[str, Any], str]:
    """The post that the press's response shows, and the ephemeral result that follows."""
    (method, post), (followup, result) = interaction.sent
    assert method == "response.edit_message"
    assert followup == "followup.send"
    assert result["ephemeral"] is True
    [embed] = cast("tuple[discord.Embed, ...]", post["embeds"])
    return embed_dict(embed), str(result["content"])


def told(interaction: FakeInteraction) -> object:
    """The text of the interaction's only response, an ephemeral reply."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_message"
    assert fields["ephemeral"] is True
    return fields["content"]


@pytest.mark.parametrize(("user", "admin"), [(7, False), (9, True)], ids=["creator", "admin"])
async def test_draw(scene: Scene, user: int, admin: bool) -> None:  # noqa: FBT001
    """Requirement: The creator or an administrator draws and administrators reroll."""
    await scene.add(GIVEAWAY)
    scene.cog.random = seeded(5)
    config = GIVEAWAY.config
    winners = draw_winners(config.prizes, config.policy, GIVEAWAY.participant_ids, seeded(5))

    clicked = await scene.click(
        "draw", GIVEAWAY.id, scene.who(user=user, admin=admin, message_id=500)
    )

    stored = await scene.stored(GIVEAWAY.id)
    assert stored == replace(GIVEAWAY, ended=True, ended_at=NOW, winner_results=winners)
    post, result = drawn(clicked)
    assert post["color"] == GOLDEN["post"]["en-US"]["drawn"]["color"]
    lines = "\n".join(
        f"{prize.prize_name}: " + " ".join(f"<@{winner}>" for winner in prize.winner_ids)
        for prize in winners
    )
    assert post["fields"][4]["value"] == lines
    assert result == f"**{GOLDEN['result']['en-US']['drawn']}**\n{lines}"


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_reroll(scene: Scene, locale: str) -> None:
    """Requirement: The creator or an administrator draws and administrators reroll."""
    await scene.add(replace(DRAWN, locale_tag=locale))
    scene.cog.random = seeded(9)
    config = GIVEAWAY.config
    winners = draw_winners(config.prizes, config.policy, GIVEAWAY.participant_ids, seeded(9))

    clicked = await scene.click("reroll", GIVEAWAY.id, scene.who(user=9, message_id=500))

    stored = await scene.stored(GIVEAWAY.id)
    assert stored.winner_results == winners  # every prize again, earlier winners included
    assert stored.ended_at == NOW
    _, result = drawn(clicked)
    assert result.startswith(f"**{GOLDEN['result'][locale]['rerolled']}**\n")


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_no_participants(scene: Scene, locale: str) -> None:
    """Requirement: The creator or an administrator draws and administrators reroll."""
    await scene.add(replace(GIVEAWAY, participant_ids=(), locale_tag=locale))

    clicked = await scene.click("draw", GIVEAWAY.id, scene.who(message_id=500))

    post, result = drawn(clicked)
    texts = GOLDEN["result"][locale]
    assert result == f"**{texts['drawn']}**\n{texts['nobody']}"
    not_enough = texts["not-enough"]
    assert post["fields"][4]["value"] == f"Nitro: {not_enough}\nSticker: {not_enough}"


@pytest.mark.parametrize(
    ("action", "giveaway", "user", "admin"),
    [
        ("draw", GIVEAWAY, 8, False),  # neither the creator nor an administrator
        ("reroll", DRAWN, 7, False),  # the creator without Administrator
    ],
    ids=["member-draws", "creator-rerolls"],
)
async def test_not_allowed(
    scene: Scene,
    action: str,
    giveaway: Instance,
    user: int,
    admin: bool,  # noqa: FBT001
) -> None:
    """Requirement: The creator or an administrator draws and administrators reroll."""
    await scene.add(replace(giveaway, locale_tag="zh-TW"))

    clicked = await scene.click(
        action, GIVEAWAY.id, scene.who(user=user, admin=admin, message_id=500)
    )

    assert told(clicked) == GOLDEN["replies"]["zh-TW"]["not-allowed"]  # the giveaway's language
    assert await scene.stored(GIVEAWAY.id) == replace(giveaway, locale_tag="zh-TW")


@pytest.mark.parametrize(
    ("action", "giveaway", "reply"),
    [
        ("draw", replace(GIVEAWAY, config=replace(GIVEAWAY.config, end_at=END)), "too-early"),
        ("draw", DRAWN, "drawn"),
        ("reroll", GIVEAWAY, "not-drawn"),
    ],
)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_wrong_time(
    scene: Scene, action: str, giveaway: Instance, reply: str, locale: str
) -> None:
    """Requirement: The creator or an administrator draws and administrators reroll."""
    await scene.add(replace(giveaway, locale_tag=locale))

    clicked = await scene.click(action, GIVEAWAY.id, scene.who(message_id=500))

    assert told(clicked) == GOLDEN["replies"][locale][reply]
    assert await scene.stored(GIVEAWAY.id) == replace(giveaway, locale_tag=locale)


async def test_draws_at_once(scene: Scene) -> None:
    """Requirement: The creator or an administrator draws and administrators reroll."""
    await scene.add(GIVEAWAY)

    first, second = await asyncio.gather(
        scene.click("draw", GIVEAWAY.id, scene.who(user=7, message_id=500)),
        scene.click("draw", GIVEAWAY.id, scene.who(user=9, message_id=500)),
    )

    outcomes = sorted(len(clicked.sent) for clicked in (first, second))
    assert outcomes == [1, 2]  # one drew, the other was told that it is drawn
    refused = first if len(first.sent) == 1 else second
    assert told(refused) == GOLDEN["replies"]["en-US"]["drawn"]


async def test_long_result(scene: Scene) -> None:
    """Requirement: The creator or an administrator draws and administrators reroll."""
    participants = tuple(range(10**17, 10**17 + 120))
    prizes = tuple(Prize(f"Prize {index}", 50) for index in range(3))
    config = replace(GIVEAWAY.config, prizes=prizes, policy=Policy.ALLOW_DUPLICATE)
    await scene.add(replace(GIVEAWAY, config=config, participant_ids=participants))

    clicked = await scene.click("draw", GIVEAWAY.id, scene.who(message_id=500))

    _, result = drawn(clicked)
    header = f"**{GOLDEN['result']['en-US']['drawn']}**\n"
    body = result.removeprefix(header)
    assert len(body) == 1800  # v3's clipFieldText(..., 1800)
    assert body.endswith("...")
