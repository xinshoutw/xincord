"""When the bot is ready, stale bindings are dropped and the rooms are checked.

Kotlin (v3 checked the bindings once, lazily, and never its rooms):
"""

import logging
from typing import TYPE_CHECKING

import discord

from discord_fakes import FakeChannel, FakeGuild, FakeVoiceChannel, forbidden
from plugin_fakes import dispatch, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.dynamic_voice_channel.store import (
    NAMESPACE,
    Binding,
    bind,
    read_bindings,
    read_rooms,
    track,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from discord_fakes import FakeRest, Sent
    from xincord.core.storage import Store

VALID = Binding(20, "Lobby", "| %dvc@custom_name%")
STALE = (
    Binding(21, "Gone"),  # the category is gone
    Binding(20, "Renamed"),  # no voice channel with that name in the category
    Binding(22, "Stage"),  # a stage channel only, which v3's voice channel lookup skipped
    Binding(30, "Lobby"),  # 30 is a voice channel, not a category
)


def checked_guild(sent: list[Sent]) -> FakeGuild:
    """Guild 10: the categories 20 and 22, the lobby, and the rooms 50 (empty) and 51 (busy)."""
    guild = FakeGuild(10, "guild")
    empty = FakeVoiceChannel(sent=sent, id=50, name="| Bob", guild=guild, category_id=20)
    busy = FakeVoiceChannel(sent=sent, id=51, name="| Ann", guild=guild, category_id=20)
    busy.voice_states[8] = object()
    guild.channels = [
        FakeChannel(id=20, name="Rooms", type=discord.ChannelType.category),
        FakeVoiceChannel(sent=sent, id=30, name="Lobby", guild=guild, category_id=20),
        empty,
        busy,
        FakeChannel(id=22, name="Stages", type=discord.ChannelType.category),
        FakeVoiceChannel(
            sent=sent,
            id=40,
            name="Stage",
            type=discord.ChannelType.stage_voice,
            guild=guild,
            category_id=22,
        ),
    ]
    return guild


async def store_guild(store: Store, guild_id: int) -> None:
    """The valid and stale bindings, and the rooms 50, 51 and 52 (gone), of ``guild_id``."""
    for binding in (*STALE[:2], VALID, *STALE[2:]):
        await bind(store, guild_id, binding)
    for room, owner in ((50, 7), (51, 8), (52, 9)):
        await track(store, guild_id, room, owner)


async def test_stale_bindings(
    bot: Bot,
    store: Store,
    rest: FakeRest,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Bindings and rooms are checked when the bot is ready."""
    await store_guild(store, 10)
    guilds = {10: checked_guild(rest.sent)}
    monkeypatch.setattr(bot, "get_guild", guilds.get)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "ready")

    assert await read_bindings(store, 10) == [VALID]
    warnings = [record.getMessage() for record in caplog.records]
    assert len(warnings) == len(STALE)
    for binding, warning in zip(STALE, warnings, strict=True):
        assert f"{binding.default_name!r} of category {binding.category_id}" in warning
        assert "guild (10)" in warning


async def test_rooms_after_a_restart(
    bot: Bot, store: Store, rest: FakeRest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Bindings and rooms are checked when the bot is ready."""
    # v3 never deleted rooms that emptied while it was away, nor forgot the deleted ones.
    await store_guild(store, 10)
    guild = checked_guild(rest.sent)
    monkeypatch.setattr(bot, "get_guild", {10: guild}.get)

    await dispatch(bot, "ready")

    assert rest.sent == [("channel.delete", {"id": 50})]
    assert await read_rooms(store, 10) == {51: 8}
    assert [channel.id for channel in guild.voice_channels] == [30, 51]


async def test_unavailable_guild(
    bot: Bot, store: Store, rest: FakeRest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Bindings and rooms are checked when the bot is ready."""
    # During an outage discord.py knows the guild without its channels.
    await store_guild(store, 10)
    await store_guild(store, 20)
    guilds = {10: checked_guild(rest.sent), 20: FakeGuild(20, unavailable=True)}
    monkeypatch.setattr(bot, "get_guild", guilds.get)

    await dispatch(bot, "ready")

    assert await read_bindings(store, 10) == [VALID]
    assert await read_bindings(store, 20) == [*STALE[:2], VALID, *STALE[2:]]
    assert await read_rooms(store, 20) == {50: 7, 51: 8, 52: 9}


async def test_deletion_refused(
    bot: Bot,
    store: Store,
    rest: FakeRest,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Bindings and rooms are checked when the bot is ready."""
    await track(store, 10, 50, 7)
    guild = checked_guild(rest.sent)
    empty = guild.get_channel(50)
    assert isinstance(empty, FakeVoiceChannel)
    empty.errors["delete"] = forbidden()
    monkeypatch.setattr(bot, "get_guild", {10: guild}.get)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "ready")

    assert await read_rooms(store, 10) == {50: 7}
    [record] = caplog.records
    assert "| Bob (50)" in record.getMessage()
    assert "guild (10)" in record.getMessage()


async def test_checked_when_loaded_into_a_ready_bot(
    store: Store, rest: FakeRest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Bindings and rooms are checked when the bot is ready."""
    await store_guild(store, 10)
    guilds = {10: checked_guild(rest.sent)}

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return guilds.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)

    bot = await load_plugin("DynamicVoiceChannel", tmp_path / "plugins", store)

    assert bot.loaded == ("DynamicVoiceChannel",)
    assert await read_bindings(store, 10) == [VALID]
    assert await read_rooms(store, 10) == {51: 8}


async def test_unreadable_data(
    bot: Bot,
    store: Store,
    rest: FakeRest,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Bindings and rooms are checked when the bot is ready."""
    # Guild 9's binding has no categoryId; guild 10's data is checked all the same.
    await store.put(NAMESPACE, "9", [{"defaultName": "Lobby"}])
    await store_guild(store, 10)
    guilds = {9: FakeGuild(9, "broken"), 10: checked_guild(rest.sent)}
    monkeypatch.setattr(bot, "get_guild", guilds.get)

    with caplog.at_level(logging.ERROR):
        await dispatch(bot, "ready")

    assert await store.get(NAMESPACE, "9") == [{"defaultName": "Lobby"}]
    assert await read_bindings(store, 10) == [VALID]
    [error] = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert "guild 9" in error.getMessage()
