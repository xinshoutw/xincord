"""Placeholder value families."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import discord
import pytest

from xincord.core.placeholders import (
    actor_values,
    channel_values,
    event_values,
    guild_values,
    locale_names,
    member_values,
    user_values,
)

CREATED = datetime(2021, 6, 1, 12, 34, 56, 789000, tzinfo=UTC)


@dataclass(frozen=True)
class Asset:
    url: str


@dataclass(frozen=True)
class User:
    id: int = 1
    name: str = "alice"
    global_name: str | None = "Alice"
    avatar: Asset | None = None
    default_avatar: Asset = Asset("https://cdn.example/default.png")
    bot: bool = False
    created_at: datetime = CREATED

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@dataclass(frozen=True)
class Role:
    name: str
    position: int
    default: bool = False

    @property
    def mention(self) -> str:
        return f"<@&{self.position}>"

    def is_default(self) -> bool:
        return self.default


@dataclass(frozen=True)
class Member(User):
    nick: str | None = "Al"
    display_avatar: Asset = Asset("https://cdn.example/guild.png")
    roles: tuple[Role, ...] = (Role("@everyone", 0, default=True),)
    joined_at: datetime | None = datetime(2022, 1, 1, tzinfo=UTC)

    @property
    def display_name(self) -> str:
        return self.nick or self.global_name or self.name


@dataclass(frozen=True)
class Channel:
    id: int = 10
    name: str = "general"
    type: discord.ChannelType = discord.ChannelType.text

    @property
    def mention(self) -> str:
        return f"<#{self.id}>"


@dataclass(frozen=True)
class Guild:
    id: int = 100
    name: str = "Guild"
    preferred_locale: discord.Locale = discord.Locale.taiwan_chinese
    member_count: int | None = 42
    premium_subscription_count: int = 3
    icon: Asset | None = None
    banner: Asset | None = None
    description: str | None = None
    owner_id: int | None = 7
    owner: Member | None = None
    system_channel: Channel | None = None
    rules_channel: Channel | None = field(default=None)


BOT = User(id=9, name="xincord", global_name=None)


def test_member_with_a_nickname() -> None:
    """Requirement: Acting-user values follow v3."""

    values = actor_values(Member(), BOT)

    assert values == {
        "bot_id": "9",
        "bot_name": "xincord",
        "user_id": "1",
        "user_mention": "<@1>",
        "user_name": "alice",
        "user_avatar_url": "https://cdn.example/default.png",
        "member_display_name": "Al",
        "member_avatar_url": "https://cdn.example/guild.png",
        "member_fixed_name": "Al (alice)",
    }


def test_plain_user() -> None:
    """Requirement: Acting-user values follow v3."""

    values = actor_values(User(avatar=Asset("https://cdn.example/a.png")), BOT)

    assert not [key for key in values if key.startswith("member_")]
    assert values["user_avatar_url"] == "https://cdn.example/a.png"


def test_member_without_a_nickname() -> None:
    """Requirement: Acting-user values follow v3."""

    assert actor_values(Member(nick=None), BOT)["member_fixed_name"] == "alice"


def test_user_keys() -> None:
    """Requirement: User and member values follow v3."""

    values = user_values(User(global_name=None), prefix="wbg@")

    assert values == {
        "wbg@user_id": "1",
        "wbg@user_name": "alice",
        "wbg@user_name_upper": "ALICE",
        "wbg@user_name_lower": "alice",
        "wbg@user_global_name": "-",
        "wbg@user_effective_name": "alice",
        "wbg@user_mention": "<@1>",
        "wbg@user_avatar_url": "https://cdn.example/default.png",
        "wbg@user_default_avatar_url": "https://cdn.example/default.png",
        "wbg@user_is_bot": "false",
        "wbg@user_created_unix": "1622550896",
        "wbg@user_created_iso": "2021-06-01T12:34:56.789Z",
    }


def test_member_roles() -> None:
    """Requirement: User and member values follow v3."""

    roles = (Role("@everyone", 0, default=True), Role("low", 1), Role("high", 5))

    values = member_values(Member(roles=roles))

    assert values == {
        "member_id": "1",
        "member_display_name": "Al",
        "member_nickname": "Al",
        "member_nickname_or_name": "Al",
        "member_avatar_url": "https://cdn.example/guild.png",
        "member_roles_count": "2",
        "member_roles_mentions": "<@&5> <@&1>",
        "member_roles_names": "high, low",
        "member_joined_unix": "1640995200",
        "member_joined_iso": "2022-01-01T00:00Z",
    }


def test_member_without_nickname_roles_or_join_time() -> None:
    """Requirement: User and member values follow v3."""

    values = member_values(Member(nick=None, joined_at=None), none="?")

    assert values["member_nickname"] == "?"
    assert values["member_nickname_or_name"] == "Alice"
    assert values["member_roles_mentions"] == "?"
    assert values["member_roles_names"] == "?"
    assert values["member_roles_count"] == "0"
    assert values["member_joined_unix"] == "0"
    assert values["member_joined_iso"] == "?"


def test_guild_without_icon_or_system_channel() -> None:
    """Requirement: Guild values follow v3."""

    values = guild_values(Guild())

    assert values == {
        "guild_id": "100",
        "guild_name": "Guild",
        "guild_name_upper": "GUILD",
        "guild_name_lower": "guild",
        "guild_locale": "CHINESE_TAIWAN",
        "guild_member_count": "42",
        "guild_boost_count": "3",
        "guild_booster_count": "3",
        "guild_icon_url": "-",
        "guild_banner_url": "-",
        "guild_description": "-",
        "guild_owner_id": "7",
        "guild_owner_name": "-",
        "guild_owner_mention": "<@7>",
        "guild_system_channel_id": "0",
        "guild_system_channel_name": "-",
        "guild_system_channel_mention": "-",
        "guild_rules_channel_id": "0",
        "guild_rules_channel_name": "-",
        "guild_rules_channel_mention": "-",
    }


def test_guild_with_everything() -> None:
    """Requirement: Guild values follow v3."""

    guild = Guild(
        preferred_locale=discord.Locale.american_english,
        member_count=None,
        icon=Asset("https://cdn.example/icon.png"),
        banner=Asset("https://cdn.example/banner.png"),
        description="  ",
        owner=Member(),
        system_channel=Channel(id=11, name="system"),
        rules_channel=Channel(id=12, name="rules"),
    )

    values = guild_values(guild, prefix="p:")

    assert values["p:guild_locale"] == "ENGLISH_US"
    assert values["p:guild_member_count"] == "0"
    assert values["p:guild_icon_url"] == "https://cdn.example/icon.png"
    assert values["p:guild_banner_url"] == "https://cdn.example/banner.png"
    assert values["p:guild_description"] == "-"
    assert values["p:guild_owner_name"] == "Al"
    assert values["p:guild_system_channel_mention"] == "<#11>"
    assert values["p:guild_rules_channel_name"] == "rules"


def test_missing_channel() -> None:
    """Requirement: Channel and event values follow v3."""

    assert channel_values(None) == {
        "channel_id": "0",
        "channel_name": "-",
        "channel_mention": "-",
        "channel_type": "-",
    }


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        (discord.ChannelType.text, "TEXT"),
        (discord.ChannelType.news, "NEWS"),
        (discord.ChannelType.public_thread, "GUILD_PUBLIC_THREAD"),
        (discord.ChannelType.forum, "FORUM"),
    ],
)
def test_channel_type_uses_jda_names(kind: discord.ChannelType, name: str) -> None:
    """Requirement: Channel and event values follow v3."""

    values = channel_values(Channel(type=kind), prefix="wbg@", base="target")

    assert values == {
        "wbg@target_id": "10",
        "wbg@target_name": "general",
        "wbg@target_mention": "<#10>",
        "wbg@target_type": name,
    }


def test_event_time() -> None:
    """Requirement: Channel and event values follow v3."""

    values = event_values("join", at=datetime(2026, 1, 2, 3, 4, 5, 678000, tzinfo=UTC))

    assert values == {
        "event_type": "join",
        "event_timestamp_unix": "1767323045",
        "event_timestamp_ms": "1767323045678",
        "event_timestamp_iso": "2026-01-02T03:04:05.678Z",
    }


def test_event_iso_keeps_seconds_and_defaults_to_now() -> None:
    """Requirement: Channel and event values follow v3."""

    at = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)

    assert event_values("x", at=at)["event_timestamp_iso"] == "2026-01-02T03:04:00Z"
    assert event_values("x", prefix="p:")["p:event_timestamp_iso"].endswith("Z")


def test_known_and_unknown_locale() -> None:
    """Requirement: Locale names follow JDA."""

    assert locale_names("en-US") == ("ENGLISH_US", "English, US")
    assert locale_names("xx") == ("UNKNOWN", "Unknown")


def discord_objects_fit(
    user: discord.User,
    member: discord.Member,
    guild: discord.Guild,
    channel: discord.TextChannel,
) -> None:
    """Type check only: discord.py's classes satisfy the placeholder Protocols."""
    actor_values(member, user)
    user_values(user)
    member_values(member)
    guild_values(guild)
    channel_values(channel)
