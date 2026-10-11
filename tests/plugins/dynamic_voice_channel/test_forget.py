"""A guild's bindings and rooms go when the bot leaves it, also while the bot was offline."""

import logging
from typing import TYPE_CHECKING

import discord

from discord_fakes import FakeChannel, FakeGuild, FakeVoiceChannel
from plugin_fakes import dispatch, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.dynamic_voice_channel.store import (
    NAMESPACE,
    ROOMS,
    Binding,
    bind,
    forget,
    guild_ids,
    track,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from discord_fakes import FakeRest, Sent
    from xincord.core.storage import Store


def available_guild(sent: list[Sent]) -> FakeGuild:
    """Guild 10 with the category 20, its lobby Lobby (30) and the occupied room 50."""
    guild = FakeGuild(10, "guild")
    lobby = FakeVoiceChannel(sent=sent, id=30, name="Lobby", guild=guild, category_id=20)
    room = FakeVoiceChannel(sent=sent, id=50, name="| Bob", guild=guild, category_id=20)
    room.voice_states[7] = object()
    category = FakeChannel(id=20, name="Rooms", type=discord.ChannelType.category)
    guild.channels = [category, lobby, room]
    return guild


async def store_three(store: Store) -> None:
    """A binding of Lobby and the room 50 in each of the guilds 10, 20 and 30."""
    for guild_id in (10, 20, 30):
        await bind(store, guild_id, Binding(20, "Lobby", "| %dvc@custom_name%"))
        await track(store, guild_id, 50, 7)


async def kept(store: Store) -> tuple[list[str], list[str]]:
    """The guilds with bindings and the guilds with rooms."""
    return await store.keys(NAMESPACE), await store.keys(ROOMS)


async def test_forget(store: Store) -> None:
    """Requirement: Data is forgotten with the guild."""
    await store_three(store)

    await forget(store, 10)

    assert await kept(store) == (["20", "30"], ["20", "30"])
    await forget(store, 10)  # nothing left to delete
    assert await kept(store) == (["20", "30"], ["20", "30"])


async def test_guild_ids(store: Store) -> None:
    """Requirement: Data is forgotten with the guild."""
    await bind(store, 12, Binding(20, "Lobby"))
    await track(store, 9, 50, 7)
    await bind(store, 10, Binding(20, "Lobby"))
    await track(store, 10, 51, 7)

    assert await guild_ids(store) == [9, 10, 12]


async def test_the_bot_leaves(bot: Bot, store: Store) -> None:
    """Requirement: Data is forgotten with the guild."""
    await store_three(store)

    await dispatch(bot, "guild_remove", FakeGuild(10).as_guild())

    # The other guilds keep their bindings and rooms.
    assert await kept(store) == (["20", "30"], ["20", "30"])


async def test_left_while_offline(
    bot: Bot,
    store: Store,
    rest: FakeRest,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Data is forgotten with the guild."""
    # Guild 20 is unavailable (an outage), not left; the bot left guild 30.
    await store_three(store)
    guilds = {10: available_guild(rest.sent), 20: FakeGuild(20, unavailable=True)}
    monkeypatch.setattr(bot, "get_guild", guilds.get)

    with caplog.at_level(logging.INFO):
        await dispatch(bot, "ready")

    assert await kept(store) == (["10", "20"], ["10", "20"])
    assert "DynamicVoiceChannel deleted the data of guild 30, which the bot left" in caplog.text
    assert rest.sent == []


async def test_loaded_into_a_ready_bot(
    store: Store, rest: FakeRest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Data is forgotten with the guild."""
    await store_three(store)
    guilds = {10: available_guild(rest.sent), 20: FakeGuild(20, unavailable=True)}

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return guilds.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)

    bot = await load_plugin("DynamicVoiceChannel", tmp_path / "plugins", store)

    assert bot.loaded == ("DynamicVoiceChannel",)
    assert await kept(store) == (["10", "20"], ["10", "20"])
