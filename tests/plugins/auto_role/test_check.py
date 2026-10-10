"""Configuration problems are logged when the bot is ready.

Kotlin (v3 resolved the roles at the first join, and dropped unknown IDs without a log):
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/AutoRole.kt:9-19
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/Event.kt:17-26
"""

import logging
from typing import TYPE_CHECKING

import discord

from discord_fakes import FakeGuild, FakeRole
from plugin_fakes import dispatch, load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.storage import Store

# Guild 10 lacks role 12 and has role 13 above the bot's; the bot lacks Manage Roles in guild 20
# and is not in guild 30. It can give the roles 11 and 21.
CONFIG = """\
guilds:
  - guild_id: 10
    role_ids: [11, 12, 13]
  - guild_id: 20
    role_ids: [21]
  - guild_id: 30
    role_ids: [31]
"""
WARNINGS = (
    "AutoRole skips role 12: it is not in guild (10)",
    (
        "AutoRole skips role booster (13) in guild (10): it is managed, @everyone or not below "
        "the bot's highest role"
    ),
    "AutoRole gives no roles in other (20): the bot lacks Manage Roles",
    "AutoRole gives no roles in guild 30: the bot is not in it",
)


def guilds() -> dict[int, FakeGuild]:
    """The guilds the bot is in, by ID."""
    return {
        10: FakeGuild(
            10, "guild", [FakeRole(11, "member"), FakeRole(13, "booster", assignable=False)]
        ),
        20: FakeGuild(20, "other", [FakeRole(21, "member")], discord.Permissions.none()),
    }


def assert_warned(caplog: pytest.LogCaptureFixture) -> None:
    """Every problem is logged, and nothing about the roles the bot can give."""
    for warning in WARNINGS:
        assert warning in caplog.text
    assert "(11)" not in caplog.text
    assert "(21)" not in caplog.text


async def test_ready(
    store: Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Problems are logged when the bot is ready."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("AutoRole", tmp_path / "plugins", store, config=CONFIG)
    assert "AutoRole" not in caplog.text  # the guilds are unknown before the bot is ready
    monkeypatch.setattr(bot, "get_guild", guilds().get)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "ready")

    assert_warned(caplog)


async def test_loaded_into_a_ready_bot(
    store: Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Problems are logged when the bot is ready."""
    found = guilds()

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return found.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)

    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("AutoRole", tmp_path / "plugins", store, config=CONFIG)

    assert bot.loaded == ("AutoRole",)
    assert_warned(caplog)


async def test_unavailable_guild(
    store: Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Problems are logged when the bot is ready."""
    config = "guilds:\n  - guild_id: 10\n    role_ids: [11]\n"
    bot = await load_plugin("AutoRole", tmp_path / "plugins", store, config=config)
    # discord.py keeps an unavailable guild without roles or members, so guild.me is None.
    monkeypatch.setattr(bot, "get_guild", {10: FakeGuild(10, "guild", unavailable=True)}.get)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "ready")

    assert "AutoRole" not in caplog.text
