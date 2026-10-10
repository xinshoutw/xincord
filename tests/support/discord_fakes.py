"""Hand-written Discord fakes and helpers for plugin tests.

Each fake has only what the plugins under test use: extend it when a plugin needs more instead of
writing another one. ``FakeInteraction.as_interaction()`` casts it for code typed with
``discord.Interaction``.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
from discord.http import HTTPClient, Route

if TYPE_CHECKING:
    from collections.abc import Mapping

    import aiohttp
    import pytest

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

    async def send_message(self, content: str | None = None, **fields: object) -> None:
        """Record a reply, such as an ephemeral one."""
        self.sent.append(("response.send_message", {"content": content, **fields}))

    async def send_modal(self, modal: discord.ui.Modal, /) -> None:
        """Record the modal that answers a button press."""
        self.sent.append(("response.send_modal", {"modal": modal}))


@dataclass
class FakeFollowup:
    """``Interaction.followup``: appends each follow-up message to the interaction's ``sent``."""

    sent: list[Sent]

    async def send(self, content: str | None = None, **fields: object) -> None:
        """Record a follow-up message, such as an ephemeral one."""
        self.sent.append(("followup.send", {"content": content, **fields}))


@dataclass
class FakeInteraction:
    """A command or component interaction that records what the plugin sends."""

    data: Mapping[str, object]
    type: discord.InteractionType = discord.InteractionType.application_command
    locale: discord.Locale = discord.Locale.american_english
    user: FakeUser | FakeMember = field(default_factory=FakeUser)
    client: object = field(default_factory=lambda: SimpleNamespace(user=BOT_USER))
    channel: object = None
    message: object = None
    command: object = None
    sent: list[Sent] = field(default_factory=list[Sent])
    guild: object = None  # None outside a guild
    guild_locale: discord.Locale | None = None  # the guild's preferred locale, in a guild
    # The permissions Discord resolved for the member in the channel.
    permissions: discord.Permissions = field(default_factory=discord.Permissions.none)

    @property
    def guild_id(self) -> int | None:
        """The guild's ID, in a guild."""
        return cast("int | None", getattr(self.guild, "id", None))

    @property
    def channel_id(self) -> int | None:
        """The ID of the channel the interaction came from."""
        return cast("int | None", getattr(self.channel, "id", None))

    @property
    def response(self) -> FakeResponse:
        """The response, recording into ``sent``."""
        return FakeResponse(self.sent)

    @property
    def followup(self) -> FakeFollowup:
        """The follow-up webhook, recording into ``sent``."""
        return FakeFollowup(self.sent)

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
    type: discord.ChannelType = discord.ChannelType.text

    @property
    def mention(self) -> str:
        """The mention markup."""
        return f"<#{self.id}>"

    async def send(self, **fields: object) -> None:
        """Record a message sent to the channel."""
        if self.error is not None:
            raise self.error
        self.sent.append(("channel.send", fields))


@dataclass
class FakeVoiceChannel(FakeChannel):
    """A voice channel of ``guild``, with the voice states of the members in it.

    ``clone``, ``delete`` and ``set_permissions`` record into ``sent``, or raise the error that
    ``errors`` holds under their name. ``clone`` sets ``cloning`` and then waits for ``gate`` when
    it is set. The copy has the ID ``id + 1000`` and joins ``guild.channels``, as discord.py caches
    it; a deleted channel leaves them.
    """

    type: discord.ChannelType = discord.ChannelType.voice
    guild: FakeGuild | None = None
    category_id: int | None = None
    voice_states: dict[int, object] = field(default_factory=dict[int, object])
    errors: dict[str, Exception] = field(default_factory=dict[str, Exception])
    gate: asyncio.Event | None = None
    cloning: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def jump_url(self) -> str:
        """The channel's URL, as discord.py builds it."""
        guild_id = 0 if self.guild is None else self.guild.id
        return f"https://discord.com/channels/{guild_id}/{self.id}"

    async def clone(
        self, *, name: str | None = None, reason: str | None = None
    ) -> FakeVoiceChannel:
        """Record the copy and return it, empty."""
        del reason
        self.cloning.set()
        if self.gate is not None:
            await self.gate.wait()
        self._fail("clone")
        self.sent.append(("channel.clone", {"id": self.id}))
        copy = FakeVoiceChannel(
            sent=self.sent,
            id=self.id + 1000,
            name=name or self.name,
            type=self.type,
            guild=self.guild,
            category_id=self.category_id,
        )
        if self.guild is not None:
            self.guild.channels.append(copy)
        return copy

    async def delete(self, *, reason: str | None = None) -> None:
        """Record the deletion."""
        del reason
        self._fail("delete")
        self.sent.append(("channel.delete", {"id": self.id}))
        if self.guild is not None and self in self.guild.channels:
            self.guild.channels.remove(self)

    async def set_permissions(
        self,
        target: FakeMember,
        *,
        overwrite: discord.PermissionOverwrite | None = None,
        reason: str | None = None,
    ) -> None:
        """Record the overwrite of ``target``."""
        del reason
        self._fail("set_permissions")
        fields: dict[str, object] = {"id": self.id, "target": target.id, "overwrite": overwrite}
        self.sent.append(("channel.set_permissions", fields))

    def _fail(self, method: str) -> None:
        if (error := self.errors.get(method)) is not None:
            raise error


def voice_state(channel: FakeChannel | None) -> discord.VoiceState:
    """A member's voice state: in ``channel``, or in no voice channel."""
    return cast("discord.VoiceState", SimpleNamespace(channel=channel))


@dataclass
class FakeRest:
    """The REST requests of discord.py's HTTP client, recorded instead of sent.

    Each is recorded in ``sent`` as ``("<method> <path>", {"json": <body>})`` and answers ``{}``
    at once; one whose ``"<method> <path>"`` is in ``errors`` raises that error instead. Pass
    ``sent`` to the fake channels to see their calls in order with the requests.
    """

    sent: list[Sent] = field(default_factory=list[Sent])
    errors: dict[str, Exception] = field(default_factory=dict[str, Exception])

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Replace ``HTTPClient.request`` with the recorder for the test."""
        recorded = self

        async def request(_http: HTTPClient, route: Route, **fields: object) -> object:
            key = f"{route.method} {route.url.removeprefix(Route.BASE)}"
            if (error := recorded.errors.get(key)) is not None:
                raise error
            recorded.sent.append((key, {"json": fields.get("json")}))
            return {}

        monkeypatch.setattr(HTTPClient, "request", request)


@dataclass
class FakeMessage:
    """A message with components that records its edits and its deletion into ``sent``.

    ``error``, when set, is raised by ``edit`` and ``delete`` instead. ``channel.fetch_message``
    returns the message itself until it is deleted, as the core fetches a message again to upgrade
    its legacy IDs.
    """

    components: list[discord.Component] = field(default_factory=list[discord.Component])
    sent: list[Sent] = field(default_factory=list[Sent])
    id: int = 42
    flags: discord.MessageFlags = field(default_factory=discord.MessageFlags)
    error: Exception | None = None
    deleted: bool = False

    @property
    def channel(self) -> SimpleNamespace:
        """The message's channel, which can fetch the message until it is deleted."""

        async def fetch_message(message_id: int, /) -> FakeMessage:
            assert message_id == self.id
            if self.deleted:
                raise not_found()
            return self

        return SimpleNamespace(fetch_message=fetch_message)

    async def edit(self, **fields: object) -> None:
        """Record an edit, or raise ``error``."""
        if self.error is not None:
            raise self.error
        self.sent.append(("message.edit", fields))

    async def delete(self) -> None:
        """Record the deletion, or raise ``error``."""
        if self.error is not None:
            raise self.error
        self.deleted = True
        self.sent.append(("message.delete", {}))

    def as_message(self) -> discord.Message:
        """This fake, typed as the discord.py message it stands for."""
        return cast("discord.Message", self)


@dataclass(frozen=True)
class FakeRole:
    """A role; ``is_assignable()`` answers ``assignable``, as discord.py's checks would."""

    id: int
    name: str = "role"
    assignable: bool = True
    position: int = 1
    default: bool = False  # the @everyone role

    @property
    def mention(self) -> str:
        """The mention markup."""
        return f"<@&{self.id}>"

    def is_assignable(self) -> bool:
        """Whether the bot could give the role: not managed, not @everyone, below its top role."""
        return self.assignable

    def is_default(self) -> bool:
        """Whether this is the @everyone role."""
        return self.default


@dataclass
class FakeGuild:
    """A guild with its roles, channels, member count and the bot's permissions there.

    It has the attributes that ``xincord.core.placeholders`` reads from guilds.
    """

    id: int = 10
    name: str = "guild"
    roles: list[FakeRole] = field(default_factory=list[FakeRole])
    permissions: discord.Permissions = field(
        default_factory=lambda: discord.Permissions(manage_roles=True)
    )
    unavailable: bool = False  # during a Discord outage
    member_count: int | None = None  # None when Discord has not sent it (unavailable since startup)
    preferred_locale: discord.Locale = discord.Locale.american_english
    channels: list[FakeChannel] = field(default_factory=list[FakeChannel])  # the cached channels
    icon: FakeAsset | None = None
    rules_channel: FakeChannel | None = None
    system_channel: FakeChannel | None = None
    premium_subscription_count: int = 0
    banner: FakeAsset | None = None
    description: str | None = None
    owner_id: int | None = None
    owner: FakeMember | None = None  # when cached

    @property
    def me(self) -> SimpleNamespace | None:
        """The bot's member in the guild, with its permissions only; None while unavailable."""
        return None if self.unavailable else SimpleNamespace(guild_permissions=self.permissions)

    def get_role(self, role_id: int, /) -> FakeRole | None:
        """The guild's role with that ID, if any."""
        return next((role for role in self.roles if role.id == role_id), None)

    def get_channel(self, channel_id: int, /) -> FakeChannel | None:
        """The guild's cached channel with that ID, if any."""
        return next((channel for channel in self.channels if channel.id == channel_id), None)

    @property
    def voice_channels(self) -> list[FakeChannel]:
        """The guild's cached voice channels, stage channels excluded."""
        return [channel for channel in self.channels if channel.type is discord.ChannelType.voice]

    def as_guild(self) -> discord.Guild:
        """This fake, typed as the discord.py guild it stands for."""
        return cast("discord.Guild", self)


type RoleRequest = tuple[tuple[int, ...], bool]  # the role IDs and the atomic flag of add_roles


@dataclass
class FakeMember:
    """A member of ``guild`` that records each ``add_roles`` call in ``requests``.

    discord.py sends one add-role request per role when ``atomic`` is true, and otherwise one
    request that replaces the member's roles. A role ID in ``errors`` makes the call raise that
    error instead. It has the attributes that ``xincord.core.placeholders`` reads from members.
    """

    guild: FakeGuild
    id: int = 1
    name: str = "alice"
    bot: bool = False
    requests: list[RoleRequest] = field(default_factory=list[RoleRequest])
    errors: dict[int, Exception] = field(default_factory=dict[int, Exception])
    global_name: str | None = None
    nick: str | None = None
    avatar: FakeAsset | None = None
    default_avatar: FakeAsset = FakeAsset("https://cdn.example/default.png")
    guild_avatar: FakeAsset | None = None
    roles: tuple[FakeRole, ...] = ()
    created_at: datetime = datetime(2021, 6, 1, tzinfo=UTC)
    joined_at: datetime | None = datetime(2022, 1, 1, tzinfo=UTC)

    @property
    def mention(self) -> str:
        """The mention markup."""
        return f"<@{self.id}>"

    @property
    def display_name(self) -> str:
        """The nickname, the global name or the username, whichever is set first."""
        return self.nick or self.global_name or self.name

    @property
    def display_avatar(self) -> FakeAsset:
        """The guild avatar, else the user's avatar, else the default one."""
        return self.guild_avatar or self.avatar or self.default_avatar

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


def not_found() -> discord.NotFound:
    """The error discord.py raises for a message or channel that is gone."""
    response = cast("aiohttp.ClientResponse", SimpleNamespace(status=404, reason="Not Found"))
    return discord.NotFound(response, "Unknown Message")


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
