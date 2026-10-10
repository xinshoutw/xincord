"""Rooms: a lobby joined alone becomes the member's room, and a copy takes its place.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/DynamicVoiceChannel.kt:94-135
"""

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.http import Route

from .names import room_name, room_values
from .store import find, read_bindings, read_rooms, track

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from discord.channel import VocalGuildChannel
    from discord.ext import commands

    from xincord.core.storage import Store

logger = logging.getLogger(__name__)

# v3's raw positions, which JDA's ChannelManager sent: the new lobby first, the room below it.
COPY_POSITION = 0
ROOM_POSITION = 1
# What the member may do in their room, on top of the lobby's overwrites (JDA's bits 4 and 28).
OWNER = discord.PermissionOverwrite(manage_channels=True, manage_permissions=True)


async def create(
    bot: commands.Bot, store: Store, member: discord.Member, lobby: VocalGuildChannel
) -> None:
    """Make ``lobby`` ``member``'s room if it is a bound lobby, and copy it as the new lobby.

    The lobby must be a voice channel (v3's ``asVoiceChannel`` threw for a stage channel) whose
    category and exact name match a binding, must not be a tracked room, and must still hold the
    member. The room is tracked once the copy exists, so that deleting it never loses the lobby:
    v3 tracked it first, and a refused copy got the lobby itself deleted. Each later step logs its
    own failure and the others still run, where v3's chain stopped at the first one.
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


async def delete(store: Store, channel: VocalGuildChannel) -> None:
    """Delete ``channel`` if it is an empty room of the plugin, and forget it."""
    raise NotImplementedError


async def _patch(bot: commands.Bot, channel: VocalGuildChannel, **fields: object) -> None:
    """Send JDA's ``PATCH /channels/<id>`` with ``fields``.

    discord.py's ``edit(position=...)`` renumbers every voice channel of the guild in one bulk
    request; JDA's ``setPosition`` sent the channel's raw position, which this keeps.
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


def _refused(action: str, channel: VocalGuildChannel, error: discord.HTTPException) -> None:
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
