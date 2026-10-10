"""v3's wbg@ placeholders for the replies and the welcome and bye messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuildSubstitutorFactory.kt:12-113
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:30-82
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:145-276
"""

import discord
import pytest

from discord_fakes import (
    BOT_USER,
    FakeAsset,
    FakeChannel,
    FakeGuild,
    FakeInteraction,
    FakeMember,
    FakeRole,
    FakeUser,
)
from xincord.plugins.welcome_bye_guild.store import Bindings
from xincord.plugins.welcome_bye_guild.values import command_values, member_event_values

# v3's keys (inventory section 7), before the wbg@ prefix.
GUILD_KEYS = (
    "guild_id",
    "guild_name",
    "guild_name_upper",
    "guild_name_lower",
    "guild_locale",
    "guild_member_count",
    "guild_boost_count",
    "guild_booster_count",
    "guild_icon_url",
    "guild_banner_url",
    "guild_description",
    "guild_owner_id",
    "guild_owner_name",
    "guild_owner_mention",
    "guild_system_channel_id",
    "guild_system_channel_name",
    "guild_system_channel_mention",
    "guild_rules_channel_id",
    "guild_rules_channel_name",
    "guild_rules_channel_mention",
)
USER_KEYS = (
    "user_id",
    "user_name",
    "user_name_upper",
    "user_name_lower",
    "user_global_name",
    "user_effective_name",
    "user_mention",
    "user_avatar_url",
    "user_default_avatar_url",
    "user_is_bot",
    "user_created_unix",
    "user_created_iso",
)
MEMBER_KEYS = (
    "member_id",
    "member_display_name",
    "member_nickname",
    "member_nickname_or_name",
    "member_avatar_url",
    "member_roles_count",
    "member_roles_mentions",
    "member_roles_names",
    "member_joined_unix",
    "member_joined_iso",
)
EVENT_KEYS = ("event_type", "event_timestamp_unix", "event_timestamp_ms", "event_timestamp_iso")
OPERATOR_KEYS = ("operator_id", "operator_name", "operator_mention")
# v3's Placeholder.get(user), then the keys that Placeholder.get(member) adds.
USER_ACTOR_KEYS = ("bot_id", "bot_name", "user_id", "user_mention", "user_name", "user_avatar_url")
MEMBER_ACTOR_KEYS = ("member_display_name", "member_avatar_url", "member_fixed_name")
# What Placeholder.get(event) adds for a command in a channel without a category.
COMMAND_KEYS = (
    "language",
    "channel_id",
    "channel_name",
    "command_name",
    "full_command_name",
    "command_string",
)


def channel_keys(base: str) -> tuple[str, ...]:
    """v3's putTextChannel keys for ``base``."""
    return tuple(f"{base}_{field}" for field in ("id", "name", "mention", "type"))


BOUND_KEYS = (
    *channel_keys("welcome_channel"),
    "welcome_channel_is_set",
    *channel_keys("bye_channel"),
    "bye_channel_is_set",
)


def prefixed(*keys: str) -> set[str]:
    """The keys with v3's wbg@ prefix."""
    return {f"wbg@{key}" for key in keys}


def subset(values: dict[str, str], expected: dict[str, str]) -> dict[str, str]:
    """The entries of ``values`` whose keys ``expected`` lists."""
    return {key: values.get(key, "<missing>") for key in expected}


def make_guild() -> FakeGuild:
    """Guild 10 with the text channels general (5) and rules (6) and an announcement channel (8)."""
    rules = FakeChannel(id=6, name="rules")
    channels = [
        FakeChannel(id=5, name="general"),
        rules,
        FakeChannel(id=8, name="news", type=discord.ChannelType.news),
    ]
    return FakeGuild(
        10,
        "guild",
        channels=channels,
        member_count=42,
        icon=FakeAsset("https://cdn.example/icon.png"),
        rules_channel=rules,
    )


def make_member(guild: FakeGuild) -> FakeMember:
    """alice, nicknamed Al, with the role Mods."""
    return FakeMember(guild, id=1, name="alice", nick="Al", roles=(FakeRole(11, "Mods"),))


def bind(guild: FakeGuild, user: FakeMember) -> FakeInteraction:
    """``/welcome-channel-bind channel: general`` run by ``user`` in general."""
    data = {
        "type": 1,
        "name": "welcome-channel-bind",
        "options": [{"type": 7, "name": "channel", "value": "5"}],
        "resolved": {"channels": {"5": {"id": "5", "name": "general"}}},
    }
    return FakeInteraction(data, user=user, channel=guild.get_channel(5), guild=guild)


def test_command_values() -> None:
    """Requirement: Templates get v3's wbg@ placeholders."""
    guild = make_guild()
    interaction = bind(guild, make_member(guild))

    values = command_values(
        interaction.as_interaction(),
        guild.as_guild(),
        Bindings(welcome=5, bye=6),
        selected=guild.get_channel(5),
    )

    assert set(values) == {
        *USER_ACTOR_KEYS,
        *MEMBER_ACTOR_KEYS,
        *COMMAND_KEYS,
        *prefixed(*GUILD_KEYS, *USER_KEYS, *MEMBER_KEYS, *EVENT_KEYS, *channel_keys("channel")),
        *prefixed(*OPERATOR_KEYS, *BOUND_KEYS, *channel_keys("old_channel")),
    }
    expected = {
        "wbg@channel_id": "5",
        "wbg@channel_name": "general",
        "wbg@channel_mention": "<#5>",
        "wbg@channel_type": "TEXT",
        "wbg@operator_id": "1",
        "wbg@operator_name": "alice",
        "wbg@operator_mention": "<@1>",
        "wbg@welcome_channel_id": "5",
        "wbg@welcome_channel_name": "general",
        "wbg@welcome_channel_mention": "<#5>",
        "wbg@welcome_channel_type": "TEXT",
        "wbg@welcome_channel_is_set": "true",
        "wbg@bye_channel_id": "6",
        "wbg@bye_channel_name": "rules",
        "wbg@bye_channel_mention": "<#6>",
        "wbg@bye_channel_is_set": "true",
        "wbg@event_type": "command",
        "wbg@guild_name": "guild",
        "wbg@guild_member_count": "42",
        "wbg@guild_rules_channel_mention": "<#6>",
        "wbg@user_name": "alice",
        "wbg@member_nickname": "Al",
        "wbg@member_roles_mentions": "<@&11>",
        "bot_name": "xincord",
        "user_name": "alice",
        "member_fixed_name": "Al (alice)",
        "command_name": "welcome-channel-bind",
        "command_string": "/welcome-channel-bind channel: #general",
        "channel_name": "general",
    }
    assert subset(values, expected) == expected


def test_bound_channels_no_longer_cached() -> None:
    """Requirement: Templates get v3's wbg@ placeholders."""
    guild = make_guild()
    interaction = bind(guild, make_member(guild))

    # 7 was deleted; 8 is an announcement channel now, which v3's getTextChannelById skipped.
    values = command_values(interaction.as_interaction(), guild.as_guild(), Bindings(7, 8))

    expected = {
        "wbg@welcome_channel_id": "7",
        "wbg@welcome_channel_mention": "<#7>",
        "wbg@welcome_channel_name": "-",
        "wbg@welcome_channel_type": "-",
        "wbg@welcome_channel_is_set": "true",
        "wbg@bye_channel_id": "8",
        "wbg@bye_channel_mention": "<#8>",
        "wbg@bye_channel_name": "-",
        "wbg@bye_channel_type": "-",
    }
    assert subset(values, expected) == expected


def test_unbound_channels_and_no_previous_channel() -> None:
    """Requirement: Templates get v3's wbg@ placeholders."""
    guild = make_guild()
    interaction = bind(guild, make_member(guild))

    values = command_values(interaction.as_interaction(), guild.as_guild(), Bindings())

    expected = {
        "wbg@channel_id": "0",
        "wbg@channel_name": "-",
        "wbg@channel_mention": "-",
        "wbg@channel_type": "-",
        "wbg@welcome_channel_id": "0",
        "wbg@welcome_channel_mention": "-",
        "wbg@welcome_channel_name": "-",
        "wbg@welcome_channel_is_set": "false",
        "wbg@bye_channel_is_set": "false",
        "wbg@old_channel_id": "0",
        "wbg@old_channel_name": "-",
        "wbg@old_channel_mention": "-",
        "wbg@old_channel_type": "-",
    }
    assert subset(values, expected) == expected


@pytest.mark.parametrize(
    ("previous", "expected"),
    [
        (5, {"id": "5", "name": "general", "mention": "<#5>", "type": "TEXT"}),
        (9, {"id": "9", "name": "-", "mention": "<#9>", "type": "-"}),  # deleted since
    ],
)
def test_previous_channel(previous: int, expected: dict[str, str]) -> None:
    """Requirement: Templates get v3's wbg@ placeholders."""
    guild = make_guild()
    interaction = bind(guild, make_member(guild))

    values = command_values(
        interaction.as_interaction(), guild.as_guild(), Bindings(), previous=previous
    )

    old = {f"wbg@old_channel_{field}": value for field, value in expected.items()}
    assert subset(values, old) == old


def test_member_event_values() -> None:
    """Requirement: Templates get v3's wbg@ placeholders."""
    guild = make_guild()

    values = member_event_values(
        BOT_USER, make_member(guild), guild.as_guild(), Bindings(welcome=5), "join"
    )

    assert set(values) == {
        *USER_ACTOR_KEYS,
        *MEMBER_ACTOR_KEYS,
        *prefixed(*GUILD_KEYS, *USER_KEYS, *MEMBER_KEYS, *EVENT_KEYS, *BOUND_KEYS),
    }
    expected = {
        "wbg@event_type": "join",
        "wbg@user_name": "alice",
        "wbg@user_effective_name": "alice",
        "wbg@member_nickname": "Al",
        "wbg@guild_member_count": "42",
        "wbg@welcome_channel_name": "general",
        "wbg@bye_channel_is_set": "false",
        "member_fixed_name": "Al (alice)",
        "bot_name": "xincord",
    }
    assert subset(values, expected) == expected


def test_departed_user() -> None:
    """Requirement: Templates get v3's wbg@ placeholders."""
    guild = make_guild()
    user = FakeUser(id=2, name="bob", global_name="Bob")

    values = member_event_values(BOT_USER, user, guild.as_guild(), Bindings(bye=6), "leave")

    assert set(values) == {
        *USER_ACTOR_KEYS,
        *prefixed(*GUILD_KEYS, *USER_KEYS, *EVENT_KEYS, *BOUND_KEYS),
    }
    expected = {
        "wbg@event_type": "leave",
        "wbg@user_name": "bob",
        "wbg@user_effective_name": "Bob",
        "wbg@bye_channel_name": "rules",
    }
    assert subset(values, expected) == expected
