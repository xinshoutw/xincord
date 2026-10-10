"""A ticket channel: its category, its permission overwrites and its first messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:248-310
"""

from typing import TYPE_CHECKING

import discord

from .texts import chunks

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterable, Mapping, Sequence

    from .model import Entry

MESSAGE_MAX = 2000  # Discord's limit of a message's text
THREADS = frozenset(
    (
        discord.ChannelType.public_thread,
        discord.ChannelType.private_thread,
        discord.ChannelType.news_thread,
    )
)


def category_of(channel: object) -> object:
    """The category of a panel's channel, a thread's parent's; None when it has none.

    v3's ``asTextChannel().parentCategory`` threw for threads and other channels; a thread's
    ``category`` raises when its parent is not cached, so the parent is read instead.
    """
    if getattr(channel, "type", None) in THREADS:
        channel = getattr(channel, "parent", None)
    return getattr(channel, "category", None)


def can_copy(
    overwrites: Iterable[discord.PermissionOverwrite],
    permissions: discord.Permissions,
    *,
    administrator: bool,
) -> bool:
    """Whether the bot may copy a category's overwrites into a new channel, as JDA's ``trySync``.

    An administrator may; otherwise each overwrite may allow or deny only permissions that the bot
    has in the category, which Discord requires of the overwrites a bot sets.
    """
    if administrator:
        return True
    held = permissions.value
    for overwrite in overwrites:
        allow, deny = overwrite.pair()
        if (allow.value | deny.value) & ~held:
            return False
    return True


def overwrites[T: Hashable](
    copied: Mapping[T, discord.PermissionOverwrite],
    *,
    everyone: T,
    member: T,
    roles: Sequence[T],
    me: T,
) -> dict[T, discord.PermissionOverwrite]:
    """A ticket channel's overwrites, built on the category's ``copied`` ones.

    As JDA's ``addPermissionOverride`` after the sync, @everyone is denied View Channel only and the
    member and each staff role allowed it only, each replacing a copied overwrite; the bot allows
    itself View Channel on top of its copied overwrite (v3 added none, so the bot needed
    Administrator or a staff role, B11).
    """
    built = dict(copied)
    built[everyone] = discord.PermissionOverwrite(view_channel=False)
    built[member] = discord.PermissionOverwrite(view_channel=True)
    for role in roles:
        built[role] = discord.PermissionOverwrite(view_channel=True)
    built[me] = viewing(copied.get(me, discord.PermissionOverwrite()), allowed=True)
    return built


def viewing(
    overwrite: discord.PermissionOverwrite, *, allowed: bool
) -> discord.PermissionOverwrite:
    """A copy of ``overwrite`` that allows or denies View Channel, its other permissions kept, as
    JDA's ``upsertPermissionOverride(...).grant`` or ``.deny``."""
    allow, deny = overwrite.pair()
    changed = discord.PermissionOverwrite.from_pair(allow, deny)
    changed.view_channel = allowed
    return changed


def is_staff(role_ids: Iterable[int], entry: Entry, *, administrator: bool) -> bool:
    """Whether a member may delete or save a ticket: they hold one of its entry's staff roles, or
    Administrator (v3's ``hasTicketAdminPermission``)."""
    return administrator or not set(entry.admin_ids).isdisjoint(role_ids)


def opener(admin_ids: Sequence[int], reason: str) -> list[str]:
    """The ticket's first messages: the staff roles' mentions, two line breaks and the reason.

    v3's text in one message, which JDA refused above 2000 characters, leaving the channel without
    its control row (B10): the text is cut into messages of at most 2000 UTF-16 code units.
    """
    mentions = "".join(f"<@&{role_id}> " for role_id in admin_ids)
    return chunks(f"{mentions}\n\n{reason}", MESSAGE_MAX)
