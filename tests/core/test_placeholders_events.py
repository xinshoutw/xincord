"""An interaction's event values and the global values."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import discord

from xincord.core.placeholders import (
    MessageLike,
    RoleLike,
    global_values,
    interaction_values,
    placeholder_values,
)


@dataclass(frozen=True)
class Asset:
    url: str


@dataclass(frozen=True)
class User:
    id: int = 1
    name: str = "alice"
    global_name: str | None = None
    avatar: Asset | None = None
    default_avatar: Asset = Asset("https://cdn.example/default.png")
    bot: bool = False
    created_at: datetime = datetime(2021, 6, 1, tzinfo=UTC)

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@dataclass(frozen=True)
class Member(User):
    nick: str | None = "Al"
    display_avatar: Asset = Asset("https://cdn.example/guild.png")
    roles: tuple[RoleLike, ...] = ()
    joined_at: datetime | None = None

    @property
    def display_name(self) -> str:
        return self.nick or self.global_name or self.name


@dataclass(frozen=True)
class Client:
    user: User | None


@dataclass(frozen=True)
class Channel:
    id: int = 10
    name: str = "general"


@dataclass
class Interaction:
    user: User
    client: Client
    data: dict[str, object] | None = field(default_factory=lambda: {"type": 1, "name": "bind"})
    locale: discord.Locale = discord.Locale.american_english
    channel: object = field(default_factory=Channel)
    message: MessageLike | None = None


BOT = User(id=99, name="xincord", bot=True)


def test_member_runs_a_command() -> None:
    """Requirement: Event values merge the user's and the interaction's."""
    values = placeholder_values(Interaction(Member(), Client(BOT)))

    assert values["bot_name"] == "xincord"
    assert values["bot_id"] == "99"
    assert values["user_name"] == "alice"
    assert values["member_fixed_name"] == "Al (alice)"
    assert values["command_string"] == "/bind"
    assert values["channel_name"] == "general"


def test_bot_not_logged_in() -> None:
    """Requirement: Event values merge the user's and the interaction's."""
    interaction = Interaction(Member(), Client(None))

    values = placeholder_values(interaction)

    assert values == interaction_values(interaction)
    assert not [key for key in values if key.startswith(("bot_", "user_", "member_"))]


def test_global_values() -> None:
    """Requirement: Global values name the bot."""
    assert global_values(Client(BOT)) == {"bot_id": "99", "bot_name": "xincord"}


def test_global_values_before_login() -> None:
    """Requirement: Global values name the bot."""
    assert global_values(Client(None)) == {}


def discord_interaction_fits(interaction: discord.Interaction) -> None:
    """Type check only: discord.py's interaction satisfies the event Protocols."""
    placeholder_values(interaction)
    global_values(interaction.client)
