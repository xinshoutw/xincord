"""The guild and the owner are checked when the bot is ready, and on a load into a ready bot.

v3 checked nothing: with its guild filter broken (B1), a wrong guild_id went unnoticed.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:24-29
"""

import logging
from typing import TYPE_CHECKING

import pytest

import payloads
from plugin_fakes import add_guild, dispatch, load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import Scene
    from xincord.core.storage import Store

CONFIG = "guild_id: 10\nuser_id: 20\nprefix: [ticket-]\ndelay_millis: 2000\n"
NO_GUILD = "TicketAwayNotice watches no channels: the bot is not in guild 10"
NO_OWNER = "TicketAwayNotice posts no notice in guild (10): user 20 is not a member"


def plugin_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The plugin's log lines at warning level and above."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("xincord.plugins.ticket_away_notice")
        and record.levelno >= logging.WARNING
    ]


async def load(store: Store, tmp_path: Path) -> Bot:
    """Load the plugin for guild 10 and owner 20, offline."""
    return await load_plugin("TicketAwayNotice", tmp_path / "plugins", store, config=CONFIG)


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The guild and the owner are checked when the bot is ready",
)
async def test_ready_without_the_guild(
    store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The guild and the owner are checked when the bot is ready."""
    with caplog.at_level(logging.WARNING):
        bot = await load(store, tmp_path)
        assert plugin_warnings(caplog) == []  # nothing is checked before the bot is ready

        await dispatch(bot, "ready")

    assert plugin_warnings(caplog) == [NO_GUILD]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The guild and the owner are checked when the bot is ready",
)
async def test_ready_without_the_owner(
    store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The guild and the owner are checked when the bot is ready."""
    bot = await load(store, tmp_path)
    add_guild(bot, payloads.guild(10, members=[payloads.member(21, "someone")]))

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "ready")

    assert plugin_warnings(caplog) == [NO_OWNER]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The guild and the owner are checked when the bot is ready",
)
async def test_ready_with_both(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The guild and the owner are checked when the bot is ready."""
    with caplog.at_level(logging.WARNING):
        await dispatch(scene.bot, "ready")

    assert plugin_warnings(caplog) == []


@pytest.mark.xfail(strict=True, reason="The guild and the owner are checked when the bot is ready")
async def test_loaded_into_a_ready_bot(
    store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The guild and the owner are checked when the bot is ready."""

    def is_ready(_bot: Bot) -> bool:
        return True  # as after /xincord reload

    monkeypatch.setattr(Bot, "is_ready", is_ready)

    with caplog.at_level(logging.WARNING):
        bot = await load(store, tmp_path)

    assert bot.loaded == ("TicketAwayNotice",)
    assert plugin_warnings(caplog) == [NO_GUILD]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The guild and the owner are checked when the bot is ready",
)
async def test_unavailable_guild(
    store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The guild and the owner are checked when the bot is ready."""
    bot = await load(store, tmp_path)
    guild = add_guild(bot, {"id": "10", "unavailable": True})  # a Discord outage
    assert guild.unavailable

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "ready")

    assert plugin_warnings(caplog) == []
