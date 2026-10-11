"""A member who joins a lobby alone gets the lobby as a room, and a copy becomes the new lobby."""

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
import pytest

from discord_fakes import (
    FakeChannel,
    FakeGuild,
    FakeMember,
    FakeVoiceChannel,
    forbidden,
    voice_state,
)
from plugin_fakes import WAIT, dispatch
from xincord.plugins.dynamic_voice_channel.store import Binding, bind, read_rooms, track

if TYPE_CHECKING:
    from discord_fakes import FakeRest, Sent
    from xincord.core.bot import Bot
    from xincord.core.storage import Store

OWNER = discord.PermissionOverwrite(manage_channels=True, manage_permissions=True)


def lobby_guild(sent: list[Sent]) -> tuple[FakeGuild, FakeVoiceChannel]:
    """Guild 10 with the category Rooms (20) and its voice channel Lobby (30)."""
    guild = FakeGuild(10, "guild")
    lobby = FakeVoiceChannel(sent=sent, id=30, name="Lobby", guild=guild, category_id=20)
    guild.channels = [FakeChannel(id=20, name="Rooms", type=discord.ChannelType.category), lobby]
    return guild, lobby


async def bind_lobby(store: Store, format_1: str = "| %dvc@custom_name%") -> None:
    """Bind the lobby of guild 10 with format 1."""
    await bind(store, 10, Binding(20, "Lobby", format_1))


def bob(guild: FakeGuild, *, is_bot: bool = False) -> FakeMember:
    """Member 7, whose display name is Bob - Gaming."""
    return FakeMember(guild, id=7, name="bob", global_name="Bob - Gaming", bot=is_bot)


async def join(bot: Bot, member: FakeMember, channel: FakeVoiceChannel) -> None:
    """``member`` joins ``channel`` from outside voice channels, as discord.py reports it."""
    channel.voice_states[member.id] = object()
    await dispatch(
        bot, "voice_state_update", member.as_member(), voice_state(None), voice_state(channel)
    )


async def cloning(task: asyncio.Task[None], lobby: FakeVoiceChannel) -> None:
    """Wait until ``task`` is copying ``lobby``, or raise the error that ended it first."""
    waiting = asyncio.create_task(lobby.cloning.wait())
    try:
        await asyncio.wait({task, waiting}, timeout=WAIT, return_when=asyncio.FIRST_COMPLETED)
    finally:
        waiting.cancel()
    if task.done():
        await task
    assert lobby.cloning.is_set()


def created(lobby_id: int = 30, name: str = "| Bob") -> list[Sent]:
    """v3's requests for a room: copy, move the copy, rename and move, permissions."""
    return [
        ("channel.clone", {"id": lobby_id}),
        (f"PATCH /channels/{lobby_id + 1000}", {"json": {"position": 0}}),
        (f"PATCH /channels/{lobby_id}", {"json": {"name": name, "position": 1}}),
        ("channel.set_permissions", {"id": lobby_id, "target": 7, "overwrite": OWNER}),
    ]


@pytest.mark.parametrize("who", ["member", "bot"])
async def test_first_join(bot: Bot, store: Store, rest: FakeRest, who: str) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    await bind_lobby(store)
    guild, lobby = lobby_guild(rest.sent)

    await join(bot, bob(guild, is_bot=who == "bot"), lobby)  # bots get rooms too, as in v3

    assert rest.sent == created()
    assert await read_rooms(store, 10) == {30: 7}
    # The copy is the new lobby; the joined channel is the room.
    assert [channel.id for channel in guild.voice_channels] == [30, 1030]


async def test_not_alone(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    await bind_lobby(store)
    guild, lobby = lobby_guild(rest.sent)
    lobby.voice_states[5] = object()

    await join(bot, bob(guild), lobby)

    assert rest.sent == []
    assert await read_rooms(store, 10) == {}


@pytest.mark.parametrize(
    "channel",
    [
        ("Other", 20, discord.ChannelType.voice),
        ("lobby", 20, discord.ChannelType.voice),
        ("Lobby", 21, discord.ChannelType.voice),
        ("Lobby", None, discord.ChannelType.voice),
        ("Lobby", 20, discord.ChannelType.stage_voice),  # v3's asVoiceChannel threw here
    ],
)
async def test_not_a_lobby(
    bot: Bot, store: Store, rest: FakeRest, channel: tuple[str, int | None, discord.ChannelType]
) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    await bind_lobby(store)
    guild = FakeGuild(10, "guild")
    name, category_id, kind = channel
    joined = FakeVoiceChannel(
        sent=rest.sent, id=30, name=name, type=kind, guild=guild, category_id=category_id
    )
    guild.channels = [joined]

    await join(bot, bob(guild), joined)

    assert rest.sent == []
    assert await read_rooms(store, 10) == {}


async def test_a_tracked_room_is_not_a_lobby(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    # A room that kept the lobby's name, as when its rename failed.
    await bind_lobby(store)
    await track(store, 10, 30, 5)
    guild, lobby = lobby_guild(rest.sent)

    await join(bot, bob(guild), lobby)

    assert rest.sent == []
    assert await read_rooms(store, 10) == {30: 5}


async def test_same_channel(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    # discord.py reports mutes, deafens and streams too; JDA's voice update did not.
    await bind_lobby(store)
    guild, lobby = lobby_guild(rest.sent)
    member = bob(guild)
    lobby.voice_states[member.id] = object()

    await dispatch(
        bot, "voice_state_update", member.as_member(), voice_state(lobby), voice_state(lobby)
    )

    assert rest.sent == []
    assert await read_rooms(store, 10) == {}


async def test_gone_before_the_plugin_saw_it(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    await bind_lobby(store)
    guild, lobby = lobby_guild(rest.sent)

    # discord.py had cached the leave before the join's listener ran.
    await dispatch(
        bot, "voice_state_update", bob(guild).as_member(), voice_state(None), voice_state(lobby)
    )

    assert rest.sent == []
    assert await read_rooms(store, 10) == {}


async def test_gone_while_the_guild_was_busy(bot: Bot, store: Store, rest: FakeRest) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    # Two lobbies of one guild: Bob's room waits for Alice's, and Bob leaves meanwhile.
    await bind_lobby(store)
    await bind(store, 10, Binding(20, "Second", "| %dvc@custom_name%"))
    guild, first = lobby_guild(rest.sent)
    first.gate = asyncio.Event()
    second = FakeVoiceChannel(sent=rest.sent, id=40, name="Second", guild=guild, category_id=20)
    guild.channels.append(second)
    alice = FakeMember(guild, id=7, name="alice", global_name="Alice")
    bob_member = FakeMember(guild, id=8, name="bob")

    alice_joins = asyncio.create_task(join(bot, alice, first))
    await cloning(alice_joins, first)  # Alice's room is being created and holds the guild
    bob_joins = asyncio.create_task(join(bot, bob_member, second))
    await asyncio.sleep(0)  # Bob's listener saw him alone and waits for the guild
    del second.voice_states[bob_member.id]
    first.gate.set()
    await asyncio.gather(alice_joins, bob_joins)

    assert rest.sent == created(name="| Alice")
    assert await read_rooms(store, 10) == {30: 7}


async def test_unusable_name(
    bot: Bot, store: Store, rest: FakeRest, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Joining an empty lobby creates a room."""
    await bind_lobby(store, format_1="   ")
    guild, lobby = lobby_guild(rest.sent)

    with caplog.at_level(logging.WARNING):
        await join(bot, bob(guild), lobby)

    # v3's setName threw here, which also skipped the move and the permissions.
    assert rest.sent == [
        ("channel.clone", {"id": 30}),
        ("PATCH /channels/1030", {"json": {"position": 0}}),
        ("PATCH /channels/30", {"json": {"position": 1}}),
        ("channel.set_permissions", {"id": 30, "target": 7, "overwrite": OWNER}),
    ]
    assert await read_rooms(store, 10) == {30: 7}
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert "Lobby (30)" in record.getMessage()
    assert "guild (10)" in record.getMessage()


async def test_copy_refused(
    bot: Bot, store: Store, rest: FakeRest, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Failures leave a lobby."""
    await bind_lobby(store)
    guild, lobby = lobby_guild(rest.sent)
    lobby.errors["clone"] = forbidden()

    with caplog.at_level(logging.WARNING):
        await join(bot, bob(guild), lobby)

    # v3 tracked the lobby anyway, and deleted it once it was empty.
    assert rest.sent == []
    assert await read_rooms(store, 10) == {}
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert "Lobby (30)" in record.getMessage()
    assert "guild (10)" in record.getMessage()


@pytest.mark.parametrize("step", [1, 2, 3])
async def test_later_step_refused(
    bot: Bot, store: Store, rest: FakeRest, caplog: pytest.LogCaptureFixture, step: int
) -> None:
    """Requirement: Failures leave a lobby."""
    await bind_lobby(store)
    guild, lobby = lobby_guild(rest.sent)
    expected = created()
    refused = expected.pop(step)
    if step == len(expected):  # the member's permissions, the last step
        lobby.errors["set_permissions"] = forbidden()
    else:
        rest.errors[refused[0]] = forbidden()

    with caplog.at_level(logging.WARNING):
        await join(bot, bob(guild), lobby)

    # v3's chain stopped at the first failure.
    assert rest.sent == expected
    assert await read_rooms(store, 10) == {30: 7}
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert f"({1030 if step == 1 else 30})" in record.getMessage()
    assert "guild (10)" in record.getMessage()
