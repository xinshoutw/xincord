"""New channels whose names start with a prefix, in the configured guild, start a notice.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:24-37
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:26-29
"""

import logging
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import golden
from xincord.plugins.ticket_away_notice.config import Config

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("ticket_away_notice")
VOICE, CATEGORY, FORUM = 2, 4, 15  # Discord's channel types


def test_prefix_match() -> None:
    """Requirement: New channels whose names start with a prefix are watched."""
    config = Config(guild_id=10, user_id=20, prefix=("ticket-", "order-"), delay_millis=2000)

    assert config.watches(10, "ticket-1")
    assert config.watches(10, "order-")
    assert not config.watches(10, "my-ticket-1")
    assert not config.watches(10, "TICKET-1")  # case-sensitive, as Kotlin's startsWith
    assert not config.watches(11, "ticket-1")  # another guild: v3's filter did not work (B1)


async def test_text_channel_with_a_prefix(scene: Scene) -> None:
    """Requirement: New channels whose names start with a prefix are watched."""
    await scene.create(31, "ticket-alice")
    await scene.settle()

    assert scene.notices() == [(31, [GOLDEN["notice"]])]


async def test_threads_and_voice_channels(scene: Scene) -> None:
    """Requirement: New channels whose names start with a prefix are watched."""
    await scene.create_thread(41, "ticket-alice")
    await scene.create(32, "order-bob", kind=VOICE)  # v3 threw for both (B2)
    await scene.settle()

    assert sorted(scene.notices()) == [(32, [GOLDEN["notice"]]), (41, [GOLDEN["notice"]])]


async def test_another_guild(scene: Scene) -> None:
    """Requirement: New channels whose names start with a prefix are watched."""
    await scene.create(51, "ticket-alice", guild_id=11)  # the owner is offline there too
    await scene.settle()

    assert scene.notices() == []
    assert scene.clock.delays == []


@pytest.mark.parametrize(
    "name",
    [
        "alice",  # a channel that Ticket opened, named after the member's username
        "my-ticket-alice",
        "TICKET-alice",
    ],
)
async def test_name_without_a_prefix(scene: Scene, name: str) -> None:
    """Requirement: New channels whose names start with a prefix are watched."""
    await scene.create(31, name)
    await scene.settle()

    assert scene.notices() == []
    assert scene.clock.delays == []


@pytest.mark.parametrize("kind", [CATEGORY, FORUM])
async def test_channels_that_take_no_messages(
    scene: Scene, kind: int, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: New channels whose names start with a prefix are watched."""
    with caplog.at_level(logging.WARNING):
        await scene.create(31, "ticket-alice", kind=kind)  # v3 threw (B2)
        await scene.settle()

    assert scene.notices() == []
    assert scene.clock.delays == []
    assert caplog.records == []


async def test_the_bots_own_thread(scene: Scene) -> None:
    """Requirement: New channels whose names start with a prefix are watched."""
    # Ticket's archive of a ticket channel named ticket-alice, in another channel.
    await scene.create_thread(41, "ticket-alice-2026-10-11", owner=99)  # the bot's user
    await scene.settle()

    assert scene.notices() == []
    assert scene.clock.delays == []
