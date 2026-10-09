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

    def as_interaction(self) -> discord.Interaction:
        """This fake, typed as the discord.py interaction it stands for."""
        return cast("discord.Interaction", self)


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
