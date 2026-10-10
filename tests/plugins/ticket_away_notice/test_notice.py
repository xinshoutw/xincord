"""The notice waits for the delay while the owner is offline, then checks again and posts.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:11-39
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/resources/lang/zh-TW/message/not-online.yaml:1-7
"""

from typing import TYPE_CHECKING

import pytest

import payloads
from plugin_fakes import golden

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("ticket_away_notice")
LOOKUP = "GET /guilds/10/members/20"  # Discord's member request for the owner


async def test_owner_offline(scene: Scene) -> None:
    """Requirement: The notice waits for the delay while the owner is offline."""
    await scene.create(31, "ticket-alice")
    await scene.clock.asleep()

    assert scene.clock.delays == [2.0]  # v3's delay_millis: 2000
    assert scene.notices() == []  # not before the wait ends

    await scene.settle()

    assert scene.notices() == [(31, [GOLDEN["notice"]])]


@pytest.mark.parametrize("status", ["online", "idle", "dnd"])
async def test_owner_online_idle_or_busy(scene: Scene, status: str) -> None:
    """Requirement: The notice waits for the delay while the owner is offline."""
    await scene.status(status)

    await scene.create(31, "ticket-alice")
    await scene.settle()

    assert scene.clock.delays == []
    assert scene.notices() == []


async def test_owner_back_during_the_wait(scene: Scene) -> None:
    """Requirement: The notice waits for the delay while the owner is offline."""
    await scene.create(31, "ticket-alice")
    await scene.clock.asleep()

    await scene.status("online")
    await scene.settle()

    assert scene.notices() == []  # v3 posted anyway


@pytest.mark.parametrize(
    ("event", "payload"),
    [
        ("CHANNEL_DELETE", payloads.channel(31, "ticket-alice", guild_id=10)),
        ("GUILD_DELETE", {"id": "10"}),  # the bot left the guild
    ],
)
async def test_channel_gone_during_the_wait(
    scene: Scene, event: str, payload: payloads.Payload
) -> None:
    """Requirement: The notice waits for the delay while the owner is offline."""
    await scene.create(31, "ticket-alice")
    await scene.clock.asleep()

    await scene.parse(event, payload)
    await scene.settle()

    assert scene.notices() == []  # v3 posted, and the request failed


async def test_owner_not_cached(scene: Scene) -> None:
    """Requirement: The notice waits for the delay while the owner is offline."""
    await scene.uncache_owner()
    # A member from Discord's REST API has no presence: discord.py says offline, as JDA did.
    scene.rest.answers[LOOKUP] = [payloads.member(20, "owner"), payloads.member(20, "owner")]

    await scene.create(31, "ticket-alice")
    await scene.settle()

    assert [key for key, _ in scene.rest.sent].count(LOOKUP) == 2  # before and after the wait
    assert scene.notices() == [(31, [GOLDEN["notice"]])]


async def test_channels_created_together(scene: Scene) -> None:
    """Requirement: The notice waits for the delay while the owner is offline."""
    await scene.create(31, "ticket-alice")
    await scene.clock.asleep()

    await scene.create(32, "order-bob")  # the first wait holds up nothing
    await scene.clock.asleep(2)
    await scene.settle()

    assert scene.clock.delays == [2.0, 2.0]
    assert sorted(channel for channel, _ in scene.notices()) == [31, 32]


@pytest.mark.parametrize("notice", [GOLDEN["operator_notice"]], ids=["operator"])
async def test_operator_v3_notice(scene: Scene) -> None:
    """Requirement: The notice waits for the delay while the owner is offline."""
    await scene.create(31, "ticket-alice")
    await scene.settle()

    # v3's layout as the operator wrote it, and v3's global placeholders.
    assert scene.notices() == [(31, [GOLDEN["operator_embed"]])]
