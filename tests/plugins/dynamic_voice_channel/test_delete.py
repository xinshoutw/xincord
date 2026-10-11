"""A room is deleted once its last member leaves."""

import asyncio
import logging
from typing import TYPE_CHECKING

import discord

from discord_fakes import (
    FakeChannel,
    FakeGuild,
    FakeMember,
    FakeVoiceChannel,
    forbidden,
    not_found,
    voice_state,
)
from plugin_fakes import WAIT, dispatch
from xincord.plugins.dynamic_voice_channel.store import Binding, bind, read_rooms, track

if TYPE_CHECKING:
    import pytest

    from discord_fakes import FakeRest, Sent
    from xincord.core.bot import Bot
    from xincord.core.storage import Store

OWNER = discord.PermissionOverwrite(manage_channels=True, manage_permissions=True)


def room_guild(sent: list[Sent]) -> tuple[FakeGuild, FakeVoiceChannel]:
    """Guild 10 with the category Rooms (20), its lobby Lobby (30) and the room | Bob (50)."""
    guild = FakeGuild(10, "guild")
    lobby = FakeVoiceChannel(sent=sent, id=30, name="Lobby", guild=guild, category_id=20)
    room = FakeVoiceChannel(sent=sent, id=50, name="| Bob", guild=guild, category_id=20)
    category = FakeChannel(id=20, name="Rooms", type=discord.ChannelType.category)
    guild.channels = [category, lobby, room]
    return guild, room


def bob(guild: FakeGuild) -> FakeMember:
    """Member 7, whose display name is Bob."""
    return FakeMember(guild, id=7, name="bob", global_name="Bob")


async def leave(bot: Bot, member: FakeMember, channel: FakeVoiceChannel) -> None:
    """``member`` leaves ``channel`` for no voice channel, as discord.py reports it."""
    channel.voice_states.pop(member.id, None)
    await dispatch(
        bot, "voice_state_update", member.as_member(), voice_state(channel), voice_state(None)
    )


async def test_last_member_leaves(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Empty rooms are deleted."""
    guild, room = room_guild(rest.sent)
    await track(store, 10, 50, 7)

    await leave(bot, bob(guild), room)

    assert rest.sent == [("channel.delete", {"id": 50})]
    assert await read_rooms(store, 10) == {}
    assert [channel.id for channel in guild.voice_channels] == [30]


async def test_move_into_a_lobby(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Empty rooms are deleted."""
    # v3 handled the joined channel first, then the left one, and so does the plugin.
    guild, room = room_guild(rest.sent)
    await bind(store, 10, Binding(20, "Lobby", "| %dvc@custom_name%"))
    await track(store, 10, 50, 7)
    lobby = guild.get_channel(30)
    assert isinstance(lobby, FakeVoiceChannel)
    member = bob(guild)
    lobby.voice_states[member.id] = object()

    await dispatch(
        bot, "voice_state_update", member.as_member(), voice_state(room), voice_state(lobby)
    )

    assert rest.sent == [
        ("channel.clone", {"id": 30}),
        ("PATCH /channels/1030", {"json": {"position": 0}}),
        ("PATCH /channels/30", {"json": {"name": "| Bob", "position": 1}}),
        ("channel.set_permissions", {"id": 30, "target": 7, "overwrite": OWNER}),
        ("channel.delete", {"id": 50}),
    ]
    assert await read_rooms(store, 10) == {30: 7}


async def test_someone_stays(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Empty rooms are deleted."""
    guild, room = room_guild(rest.sent)
    await track(store, 10, 50, 7)
    room.voice_states[5] = object()

    await leave(bot, bob(guild), room)

    assert rest.sent == []
    assert await read_rooms(store, 10) == {50: 7}


async def test_untracked_channel(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Empty rooms are deleted."""
    guild, room = room_guild(rest.sent)
    await track(store, 10, 51, 8)

    await leave(bot, bob(guild), room)

    assert rest.sent == []
    assert await read_rooms(store, 10) == {51: 8}


async def test_already_deleted(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Empty rooms are deleted."""
    guild, room = room_guild(rest.sent)
    await track(store, 10, 50, 7)
    room.errors["delete"] = not_found()

    await leave(bot, bob(guild), room)

    assert await read_rooms(store, 10) == {}


async def test_deletion_refused(
    bot: Bot, store: Store, rest: FakeRest, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Empty rooms are deleted."""
    guild, room = room_guild(rest.sent)
    await track(store, 10, 50, 7)
    room.errors["delete"] = forbidden()

    with caplog.at_level(logging.WARNING):
        await leave(bot, bob(guild), room)

    # v3 forgot the room anyway, and never tried again.
    assert await read_rooms(store, 10) == {50: 7}
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert "| Bob (50)" in record.getMessage()
    assert "guild (10)" in record.getMessage()


async def test_leaving_during_the_creation(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Empty rooms are deleted."""
    # v3 tracked the room in memory at once and in MongoDB later, and read MongoDB on the leave.
    guild, _ = room_guild(rest.sent)
    await bind(store, 10, Binding(20, "Lobby", "| %dvc@custom_name%"))
    lobby = guild.get_channel(30)
    assert isinstance(lobby, FakeVoiceChannel)
    lobby.gate = asyncio.Event()
    member = bob(guild)
    lobby.voice_states[member.id] = object()
    joins = asyncio.create_task(
        dispatch(
            bot, "voice_state_update", member.as_member(), voice_state(None), voice_state(lobby)
        )
    )
    waiting = asyncio.create_task(lobby.cloning.wait())
    await asyncio.wait({joins, waiting}, timeout=WAIT, return_when=asyncio.FIRST_COMPLETED)
    waiting.cancel()
    if joins.done():
        await joins  # the creation failed: raise its error

    leaves = asyncio.create_task(leave(bot, member, lobby))
    await asyncio.sleep(0)  # the leave's listener waits for the guild
    lobby.gate.set()
    await asyncio.gather(joins, leaves)

    assert rest.sent == [
        ("channel.clone", {"id": 30}),
        ("PATCH /channels/1030", {"json": {"position": 0}}),
        ("PATCH /channels/30", {"json": {"name": "| Bob", "position": 1}}),
        ("channel.set_permissions", {"id": 30, "target": 7, "overwrite": OWNER}),
        ("channel.delete", {"id": 30}),
    ]
    assert await read_rooms(store, 10) == {}
    assert [channel.id for channel in guild.voice_channels] == [50, 1030]  # the copy is the lobby
