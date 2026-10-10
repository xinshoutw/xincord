"""Hand-written Discord fakes and helpers for plugin tests.

Each fake has only what the plugins under test use: extend it when a plugin needs more instead of
writing another one. ``FakeInteraction.as_interaction()`` casts it for code typed with
``discord.Interaction``.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord

if TYPE_CHECKING:
    from collections.abc import Mapping

    import aiohttp

type Sent = tuple[str, dict[str, object]]  # the method and the keyword arguments of a response


@dataclass(frozen=True)
class FakeAsset:
    """An avatar."""

    url: str


@dataclass(frozen=True)
class FakeUser:
    """A user with the attributes that ``xincord.core.placeholders`` reads."""

    id: int = 1
    name: str = "alice"
    global_name: str | None = None
    avatar: FakeAsset | None = None
    default_avatar: FakeAsset = FakeAsset("https://cdn.example/default.png")
    bot: bool = False
    created_at: datetime = datetime(2021, 6, 1, tzinfo=UTC)

    @property
    def mention(self) -> str:
        """The mention markup."""
        return f"<@{self.id}>"


BOT_USER = FakeUser(id=99, name="xincord", bot=True)


@dataclass
class FakeResponse:
    """``Interaction.response``: appends each response to the interaction's ``sent`` list."""

    sent: list[Sent]

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        """Record a deferral, such as the command tree's before a command runs."""
        self.sent.append(("response.defer", {"ephemeral": ephemeral, "thinking": thinking}))

    async def edit_message(self, **fields: object) -> None:
        """Record an edit of the component's message."""
        self.sent.append(("response.edit_message", fields))


@dataclass
class FakeInteraction:
    """A command or component interaction that records what the plugin sends."""

    data: Mapping[str, object]
    type: discord.InteractionType = discord.InteractionType.application_command
    locale: discord.Locale = discord.Locale.american_english
    user: FakeUser = field(default_factory=FakeUser)
    client: object = field(default_factory=lambda: SimpleNamespace(user=BOT_USER))
    channel: object = None
    message: object = None
    command: object = None
    sent: list[Sent] = field(default_factory=list[Sent])

    @property
    def response(self) -> FakeResponse:
        """The response, recording into ``sent``."""
        return FakeResponse(self.sent)

    async def edit_original_response(self, **fields: object) -> None:
        """Record an edit of the deferred response."""
        self.sent.append(("edit_original_response", fields))

    async def delete_original_response(self) -> None:
        """Record the deletion of the deferred response."""
        self.sent.append(("delete_original_response", {}))

    def as_interaction(self) -> discord.Interaction:
        """This fake, typed as the discord.py interaction it stands for."""
        return cast("discord.Interaction", self)


@dataclass
class FakeChannel:
    """A text channel that records sent messages into ``sent``, or fails with ``error``.

    Pass the interaction's ``sent`` list to see the channel's messages in order with the responses.
    """

    sent: list[Sent] = field(default_factory=list[Sent])
    error: Exception | None = None
    id: int = 5
    name: str = "general"

    async def send(self, **fields: object) -> None:
        """Record a message sent to the channel."""
        if self.error is not None:
            raise self.error
        self.sent.append(("channel.send", fields))


@dataclass(frozen=True)
class FakeRole:
    """A role; ``is_assignable()`` answers ``assignable``, as discord.py's checks would."""

    id: int
    name: str = "role"
    assignable: bool = True

    def is_assignable(self) -> bool:
        """Whether the bot could give the role: not managed, not @everyone, below its top role."""
        return self.assignable


@dataclass
class FakeGuild:
    """A guild with its roles and the bot's permissions there."""

    id: int = 10
    name: str = "guild"
    roles: list[FakeRole] = field(default_factory=list[FakeRole])
    permissions: discord.Permissions = field(
        default_factory=lambda: discord.Permissions(manage_roles=True)
    )
    unavailable: bool = False  # during a Discord outage

    @property
    def me(self) -> SimpleNamespace | None:
        """The bot's member in the guild, with its permissions only; None while unavailable."""
        return None if self.unavailable else SimpleNamespace(guild_permissions=self.permissions)

    def get_role(self, role_id: int, /) -> FakeRole | None:
        """The guild's role with that ID, if any."""
        return next((role for role in self.roles if role.id == role_id), None)


type RoleRequest = tuple[tuple[int, ...], bool]  # the role IDs and the atomic flag of add_roles


@dataclass
class FakeMember:
    """A member of ``guild`` that records each ``add_roles`` call in ``requests``.

    discord.py sends one add-role request per role when ``atomic`` is true, and otherwise one
    request that replaces the member's roles. A role ID in ``errors`` makes the call raise that
    error instead.
    """

    guild: FakeGuild
    id: int = 1
    name: str = "alice"
    bot: bool = False
    requests: list[RoleRequest] = field(default_factory=list[RoleRequest])
    errors: dict[int, Exception] = field(default_factory=dict[int, Exception])

    async def add_roles(self, *roles: FakeRole, atomic: bool = True) -> None:
        """Record the request, or raise the error set for one of the roles."""
        for role in roles:
            if (error := self.errors.get(role.id)) is not None:
                raise error
        self.requests.append((tuple(role.id for role in roles), atomic))

    def as_member(self) -> discord.Member:
        """This fake, typed as the discord.py member it stands for."""
        return cast("discord.Member", self)


def forbidden() -> discord.Forbidden:
    """The error discord.py raises when the bot lacks a permission."""
    response = cast("aiohttp.ClientResponse", SimpleNamespace(status=403, reason="Forbidden"))
    return discord.Forbidden(response, "Missing Permissions")


def embed_dict(embed: discord.Embed) -> dict[str, Any]:
    """``embed.to_dict()`` without the keys discord.py always adds (``type``, ``flags``)."""
    return {key: value for key, value in embed.to_dict().items() if key not in {"type", "flags"}}


def buttons(view: object) -> list[tuple[str | None, str | None]]:
    """The label and the custom ID of each button in a rendered view."""
    assert isinstance(view, discord.ui.View)
    found: list[tuple[str | None, str | None]] = []
    for item in view.children:
        assert isinstance(item, discord.ui.Button)
        found.append((item.label, item.custom_id))
    return found
