"""Rooms: a lobby joined alone becomes the member's room, and a copy takes its place.

Rooms are deleted once they are empty, and a guild's bindings and rooms are checked when the bot
is ready.
"""

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import discord
from discord.http import Route

from .names import room_name, room_values
from .store import drop, find, read_bindings, read_rooms, track, untrack

if TYPE_CHECKING:
    from collections.abc import Coroutine, Mapping

    from discord.channel import VocalGuildChannel
    from discord.ext import commands

    from xincord.core.storage import Store

    from .store import Binding

logger = logging.getLogger(__name__)

# The raw positions sent: the new lobby first, the room below it.
COPY_POSITION = 0
ROOM_POSITION = 1
# What the member may do in their room, on top of the lobby's overwrites (bits 4 and 28).
OWNER = discord.PermissionOverwrite(manage_channels=True, manage_permissions=True)


@runtime_checkable
class Room(Protocol):
    """A voice channel, as the plugin deletes rooms."""

    @property
    def id(self) -> int:
        """The channel ID."""
        ...

    @property
    def name(self) -> str:
        """The channel's name."""
        ...

    @property
    def guild(self) -> discord.Guild:
        """The channel's guild."""
        ...

    @property
    def voice_states(self) -> Mapping[int, object]:
        """The voice states of the members in the channel, by member ID."""
        ...

    async def delete(self, *, reason: str | None = None) -> None:
        """Delete the channel."""
        ...


async def create(
    bot: commands.Bot, store: Store, member: discord.Member, lobby: VocalGuildChannel
) -> None:
    """Make ``lobby`` ``member``'s room if it is a bound lobby, and copy it as the new lobby.

    The lobby must be a voice channel, not a stage channel, whose
    category and exact name match a binding, must not be a tracked room, and must still hold the
    member. The room is tracked once the copy exists, so that deleting it never loses the lobby.
    Each later step logs its own failure and the others still run.
    """
    guild = lobby.guild
    if lobby.type is not discord.ChannelType.voice or lobby.category_id is None:
        return
    binding = find(await read_bindings(store, guild.id), lobby.category_id, lobby.name)
    if binding is None or lobby.id in await read_rooms(store, guild.id):
        return
    if member.id not in lobby.voice_states:  # gone while the guild's other changes ran
        return
    try:
        copy = await lobby.clone()
    except discord.HTTPException as error:
        _refused("copy the lobby", lobby, error)
        return
    await track(store, guild.id, lobby.id, member.id)
    await _attempt("move the new lobby", copy, _patch(bot, copy, position=COPY_POSITION))
    bot_user = bot.user
    values = {} if bot_user is None else room_values(member, bot_user)
    name = room_name(binding.format_name_1, values)
    if name is None:
        logger.warning(
            "DynamicVoiceChannel keeps the name of the room %s (%s) of %s (%s): format 1 gives an"
            " empty name or one over 100 characters",
            lobby.name,
            lobby.id,
            guild.name,
            guild.id,
        )
    rename = {} if name is None else {"name": name}
    await _attempt(
        "rename and move the room", lobby, _patch(bot, lobby, **rename, position=ROOM_POSITION)
    )
    await _attempt(
        f"give {member.display_name} ({member.id}) the permissions of the room",
        lobby,
        lobby.set_permissions(member, overwrite=OWNER),
    )


async def delete(store: Store, channel: Room) -> None:
    """Delete ``channel`` if it is an empty room of the plugin, and forget it.

    Emptiness is checked last, right before the request, so that a member who joined meanwhile
    keeps the room. A room that Discord no longer has is
    forgotten; one that Discord refuses to delete stays tracked with a warning, so that the next
    leave or READY tries again. Untracked channels are never deleted.
    """
    guild = channel.guild
    if channel.id not in await read_rooms(store, guild.id) or channel.voice_states:
        return
    try:
        await channel.delete()
    except discord.NotFound:
        pass  # deleted already: forget it
    except discord.HTTPException as error:
        _refused("delete the room", channel, error)
        return
    await untrack(store, guild.id, channel.id)


async def check(store: Store, guild: discord.Guild) -> None:
    """Drop the guild's stale bindings, delete its empty rooms and forget its missing ones.

    A binding goes when its category is gone or holds no voice channel with the lobby's exact name,
    with a warning. Rooms that emptied while the bot was away are deleted, and the records of
    deleted ones forgotten.
    """
    stale: list[Binding] = []
    for binding in await read_bindings(store, guild.id):
        if (reason := _missing(guild, binding)) is not None:
            logger.warning(
                "DynamicVoiceChannel unbound the lobby %r of category %s in %s (%s): %s",
                binding.default_name,
                binding.category_id,
                guild.name,
                guild.id,
                reason,
            )
            stale.append(binding)
    if stale:
        await drop(store, guild.id, {binding.key for binding in stale})
    for room_id in await read_rooms(store, guild.id):
        channel = guild.get_channel(room_id)
        if isinstance(channel, Room):
            await delete(store, channel)
        else:  # deleted while the bot was away
            await untrack(store, guild.id, room_id)


def _missing(guild: discord.Guild, binding: Binding) -> str | None:
    """Why ``binding``'s lobby no longer exists in ``guild``, or None when it does.

    Voice channels match by exact name, stage channels excluded.
    """
    category = guild.get_channel(binding.category_id)
    if category is None or category.type is not discord.ChannelType.category:
        return "the category does not exist"
    if not any(
        channel.category_id == binding.category_id and channel.name == binding.default_name
        for channel in guild.voice_channels
    ):
        return "the category has no voice channel with that name"
    return None


async def _patch(bot: commands.Bot, channel: VocalGuildChannel, **fields: object) -> None:
    """Send ``PATCH /channels/<id>`` with ``fields``.

    discord.py's ``edit(position=...)`` renumbers every voice channel of the guild in one bulk
    request; this sends the channel's raw position.
    """
    route = Route("PATCH", "/channels/{channel_id}", channel_id=channel.id)
    await bot.http.request(route, json=fields)


async def _attempt(
    action: str, channel: VocalGuildChannel, request: Coroutine[Any, Any, object]
) -> None:
    """Send ``request``, and log a warning when Discord refuses it."""
    try:
        await request
    except discord.HTTPException as error:
        _refused(action, channel, error)


def _refused(action: str, channel: Room, error: discord.HTTPException) -> None:
    """Log that Discord refused ``action`` on ``channel``, naming the guild and the channel."""
    guild = channel.guild
    logger.warning(
        "DynamicVoiceChannel cannot %s %s (%s) of %s (%s): %s",
        action,
        channel.name,
        channel.id,
        guild.name,
        guild.id,
        error,
    )
