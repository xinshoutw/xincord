"""Guild messages that the plugin stores, as discord.py parses them from the gateway."""

from typing import TYPE_CHECKING

import pytest

import payloads
from discord_fakes import BOT_USER

if TYPE_CHECKING:
    from conftest import Scene


async def test_stored_message(scene: Scene) -> None:
    """Requirement: Guild messages are stored."""
    await scene.send(100, 30, "hello")
    await scene.send(101, 41, "in a thread")  # threads too, as in v3
    await scene.send(102, 99, "uncached")  # a channel that discord.py has not cached

    assert await scene.rows() == [
        (100, 10, 30, 7, "hello", 0),
        (101, 10, 41, 7, "in a thread", 0),
        (102, 10, 99, 7, "uncached", 0),
    ]


async def test_bots_and_webhooks(scene: Scene) -> None:
    """Requirement: Guild messages are stored."""
    other_bot = payloads.user(8, "helper", bot=True)
    webhook = payloads.user(500, "hook", bot=True)
    embed: payloads.Payload = {"type": "rich", "title": "T"}
    bot_message = payloads.message(100, 30, 10, other_bot, "beep", embeds=[embed])
    await scene.parse("MESSAGE_CREATE", bot_message)
    await scene.parse(
        "MESSAGE_CREATE", payloads.message(101, 30, 10, webhook, "hi", webhook_id=500)
    )

    # v3 stored other bots' and webhooks' messages; a webhook's author is the webhook. Their rich
    # embeds are part of the text.
    assert await scene.rows() == [(100, 10, 30, 8, "beep\n\nT", 0), (101, 10, 30, 500, "hi", 0)]


async def test_the_bots_own_message(scene: Scene) -> None:
    """Requirement: Guild messages are stored."""
    await scene.send(100, 30, "posted by the bot", author=BOT_USER.id)

    assert await scene.rows() == []


@pytest.mark.parametrize("config", ["log_all: false\n"])
async def test_only_detected_channels(scene: Scene) -> None:
    """Requirement: Guild messages are stored."""
    await scene.listen(5, [30])

    await scene.send(100, 30, "detected")
    await scene.send(101, 41, "in a thread of 30")
    await scene.send(102, 32, "not detected")

    # v3 stored only the channels that had a table already, which no setting changed.
    assert [row[0] for row in await scene.rows()] == [100, 101]


async def test_direct_message(scene: Scene) -> None:
    """Requirement: Guild messages are stored."""
    await scene.parse("MESSAGE_CREATE", payloads.message(100, 50, None, payloads.user(7), "hi"))

    assert await scene.rows() == []
