"""The ``wbg@`` placeholders for the replies and the welcome and bye messages."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import discord

from xincord.core.placeholders import (
    GuildLike,
    MemberLike,
    actor_values,
    channel_values,
    event_values,
    guild_values,
    member_values,
    placeholder_values,
    user_values,
)

from .store import KINDS

if TYPE_CHECKING:
    from xincord.core.placeholders import UserLike

    from .store import Bindings

PREFIX = "wbg@"  # the prefix of the plugin's keys
NONE = "-"  # the text for a missing value


@runtime_checkable
class TextChannelLike(Protocol):
    """A guild channel as the placeholders read it; its type tells text channels apart."""

    @property
    def id(self) -> int:
        """The channel ID."""
        ...

    @property
    def name(self) -> str:
        """The channel name."""
        ...

    @property
    def mention(self) -> str:
        """The mention markup."""
        ...

    @property
    def type(self) -> discord.ChannelType:
        """The channel type."""
        ...


class GuildChannels(GuildLike, Protocol):
    """A guild as the placeholders read it, with its cached channels; ``discord.Guild`` is one."""

    def get_channel(self, channel_id: int, /) -> object:
        """The cached channel with that ID, if any."""
        ...


def text_channel(channel: object) -> TextChannelLike | None:
    """Return ``channel`` if it is a text channel.

    Announcement channels, threads, voice and stage channels and forums are not. ``channel`` may
    be a discord.py channel, the channel of a command option or None.
    """
    if isinstance(channel, TextChannelLike) and channel.type == discord.ChannelType.text:
        return channel
    return None


def command_values(
    interaction: discord.Interaction,
    guild: GuildChannels,
    bindings: Bindings,
    *,
    selected: TextChannelLike | None = None,
    previous: int = 0,
) -> dict[str, str]:
    """Return the values for a reply in ``guild``.

    Args:
        interaction: The command.
        guild: The command's guild.
        bindings: The guild's channels after the command.
        selected: The channel the command chose, for ``wbg@channel_*``.
        previous: The channel bound before an unbind, for ``wbg@old_channel_*``; 0 for none.
    """
    user = interaction.user
    operator = {
        f"{PREFIX}operator_id": str(user.id),
        f"{PREFIX}operator_name": user.name,
        f"{PREFIX}operator_mention": user.mention,
    }
    return (
        placeholder_values(interaction)
        | _subject_values(user, guild, "command")
        | channel_values(selected, PREFIX, "channel", NONE)
        | operator
        | _bound_values(guild, bindings)
        | _stored_channel_values(guild, "old_channel", previous)
    )


def member_event_values(
    bot: UserLike | None,
    user: UserLike,
    guild: GuildChannels,
    bindings: Bindings,
    event_type: str,
) -> dict[str, str]:
    """Return the values for a welcome or bye message.

    Args:
        bot: The bot's user; None before it has logged in.
        user: The member who joined or left, or the user who left when discord.py had not cached
            the member.
        guild: The member's guild.
        bindings: The guild's channels.
        event_type: ``join`` or ``leave``.
    """
    # The member's placeholder values, or the user's for a departed user.
    actor = {} if bot is None else actor_values(user, bot)
    return actor | _subject_values(user, guild, event_type) | _bound_values(guild, bindings)


def _subject_values(user: UserLike, guild: GuildLike, event_type: str) -> dict[str, str]:
    """The ``wbg@`` keys of the guild, the user, the member when ``user`` is one, and the event."""
    member = member_values(user, PREFIX) if isinstance(user, MemberLike) else {}
    return (
        guild_values(guild, PREFIX)
        | user_values(user, PREFIX)
        | member
        | event_values(event_type, PREFIX)
    )


def _bound_values(guild: GuildChannels, bindings: Bindings) -> dict[str, str]:
    """The ``wbg@welcome_channel_*`` and ``wbg@bye_channel_*`` keys, with ``*_is_set``."""
    values: dict[str, str] = {}
    for kind in KINDS:
        channel_id = bindings.channel(kind)
        values |= _stored_channel_values(guild, f"{kind}_channel", channel_id)
        values[f"{PREFIX}{kind}_channel_is_set"] = "true" if channel_id else "false"
    return values


def _stored_channel_values(guild: GuildChannels, base: str, channel_id: int) -> dict[str, str]:
    """The ``wbg@<base>_*`` keys of a stored channel ID, 0 when unbound.

    The ID and the mention come from the stored ID, also for a deleted channel; the name and the
    type from the guild's cached text channel, else ``-``.
    """
    cached = text_channel(guild.get_channel(channel_id)) if channel_id else None
    return channel_values(cached, PREFIX, base, NONE) | {
        f"{PREFIX}{base}_id": str(channel_id),
        f"{PREFIX}{base}_mention": f"<#{channel_id}>" if channel_id else NONE,
    }
