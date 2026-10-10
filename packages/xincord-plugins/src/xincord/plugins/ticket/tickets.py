"""A ticket channel: its category, its permission overwrites and its first messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:248-310
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterable, Mapping, Sequence

    import discord


def category_of(channel: object) -> object:
    """The category of a panel's channel, a thread's parent's; None when it has none."""
    raise NotImplementedError


def can_copy(
    overwrites: Iterable[discord.PermissionOverwrite],
    permissions: discord.Permissions,
    *,
    administrator: bool,
) -> bool:
    """Whether the bot may copy a category's overwrites into a new channel, as JDA's ``trySync``."""
    raise NotImplementedError


def overwrites[T: Hashable](
    copied: Mapping[T, discord.PermissionOverwrite],
    *,
    everyone: T,
    member: T,
    roles: Sequence[T],
    me: T,
) -> dict[T, discord.PermissionOverwrite]:
    """A ticket channel's overwrites, built on the category's ``copied`` ones."""
    raise NotImplementedError


def opener(admin_ids: Sequence[int], reason: str) -> list[str]:
    """The ticket's first messages: the staff roles' mentions, two line breaks and the reason."""
    raise NotImplementedError
