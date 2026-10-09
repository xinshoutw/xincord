"""``%key%`` placeholders: single-pass rendering and the v3 key families."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    import discord


class AssetLike(Protocol):
    """An image asset, such as :class:`discord.Asset`."""

    @property
    def url(self) -> str:
        """The asset's URL."""
        ...


class UserLike(Protocol):
    """The parts of :class:`discord.User` that placeholders read."""

    @property
    def id(self) -> int:
        """The user ID."""
        ...

    @property
    def name(self) -> str:
        """The unique username."""
        ...

    @property
    def global_name(self) -> str | None:
        """The global display name, if set."""
        ...

    @property
    def mention(self) -> str:
        """The mention markup."""
        ...

    @property
    def avatar(self) -> AssetLike | None:
        """The custom avatar, if set."""
        ...

    @property
    def default_avatar(self) -> AssetLike:
        """The default avatar."""
        ...

    @property
    def bot(self) -> bool:
        """Whether the user is a bot."""
        ...

    @property
    def created_at(self) -> datetime:
        """When the account was created (aware, UTC)."""
        ...


class RoleLike(Protocol):
    """The parts of :class:`discord.Role` that placeholders read."""

    @property
    def name(self) -> str:
        """The role name."""
        ...

    @property
    def mention(self) -> str:
        """The mention markup."""
        ...

    @property
    def position(self) -> int:
        """The position in the role list; higher is more important."""
        ...

    def is_default(self) -> bool:
        """Whether this is the @everyone role."""
        ...


@runtime_checkable
class MemberLike(UserLike, Protocol):
    """The parts of :class:`discord.Member` that placeholders read."""

    @property
    def nick(self) -> str | None:
        """The guild nickname, if set."""
        ...

    @property
    def display_name(self) -> str:
        """The nickname, global name or username, whichever is set first."""
        ...

    @property
    def display_avatar(self) -> AssetLike:
        """The guild avatar, else the user's avatar."""
        ...

    @property
    def roles(self) -> Sequence[RoleLike]:
        """The member's roles, including the default role."""
        ...

    @property
    def joined_at(self) -> datetime | None:
        """When the member joined the guild."""
        ...


class ChannelLike(Protocol):
    """The parts of a discord.py guild channel that placeholders read."""

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


class GuildLike(Protocol):
    """The parts of :class:`discord.Guild` that placeholders read."""

    @property
    def id(self) -> int:
        """The guild ID."""
        ...

    @property
    def name(self) -> str:
        """The guild name."""
        ...

    @property
    def preferred_locale(self) -> discord.Locale:
        """The community's preferred locale."""
        ...

    @property
    def member_count(self) -> int | None:
        """The member count, when known."""
        ...

    @property
    def premium_subscription_count(self) -> int:
        """The number of boosts."""
        ...

    @property
    def icon(self) -> AssetLike | None:
        """The icon, if set."""
        ...

    @property
    def banner(self) -> AssetLike | None:
        """The banner, if set."""
        ...

    @property
    def description(self) -> str | None:
        """The description, if set."""
        ...

    @property
    def owner_id(self) -> int | None:
        """The owner's user ID."""
        ...

    @property
    def owner(self) -> MemberLike | None:
        """The owner, when cached."""
        ...

    @property
    def system_channel(self) -> ChannelLike | None:
        """The system messages channel, if set."""
        ...

    @property
    def rules_channel(self) -> ChannelLike | None:
        """The rules channel, if set."""
        ...


def render(text: str, values: Mapping[str, str]) -> str:
    """Replace each ``%key%`` that has a value, in one left-to-right pass.

    Keys without a value stay as written, ``$%`` is a literal ``%``, and substituted values are
    never scanned again.
    """
    out: list[str] = []
    index = 0
    while (start := text.find("%", index)) != -1:
        if start > index and text[start - 1] == "$":
            out += (text[index : start - 1], "%")
            index = start + 1
            continue
        end = text.find("%", start + 1)
        if end == -1:
            break
        out.append(text[index:start])
        key = text[start + 1 : end]
        if key in values:
            out.append(values[key])
            index = end + 1
        else:
            # The closing % may open the next placeholder, as in commons-text.
            out.append(text[start:end])
            index = end
    out.append(text[index:])
    return "".join(out)


def actor_values(user: UserLike, bot: UserLike) -> dict[str, str]:
    """Return the v3 ``Placeholder.get`` keys for the user acting in an interaction."""
    raise NotImplementedError


def user_values(user: UserLike, prefix: str = "", none: str = "-") -> dict[str, str]:
    """Return the v3 ``putUser`` keys, each prefixed with ``prefix``."""
    raise NotImplementedError


def member_values(member: MemberLike, prefix: str = "", none: str = "-") -> dict[str, str]:
    """Return the v3 ``putMember`` keys, each prefixed with ``prefix``."""
    raise NotImplementedError


def guild_values(guild: GuildLike, prefix: str = "", none: str = "-") -> dict[str, str]:
    """Return the v3 ``putGuild`` keys, each prefixed with ``prefix``."""
    raise NotImplementedError


def channel_values(
    channel: ChannelLike | None,
    prefix: str = "",
    base: str = "channel",
    none: str = "-",
) -> dict[str, str]:
    """Return the v3 ``putTextChannel`` keys ``<base>_id``, ``_name``, ``_mention``, ``_type``."""
    raise NotImplementedError


def event_values(event_type: str, prefix: str = "", at: datetime | None = None) -> dict[str, str]:
    """Return the v3 ``putEvent`` keys for an event at ``at`` (default: now)."""
    raise NotImplementedError


def locale_names(locale: str) -> tuple[str, str]:
    """Return JDA's enum name and native name of a Discord locale such as ``zh-TW``."""
    raise NotImplementedError
