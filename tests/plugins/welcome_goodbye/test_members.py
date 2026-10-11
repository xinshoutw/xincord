"""Welcome and bye messages in the bound channels when members join or leave."""

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import (
    BOT_USER,
    FakeAsset,
    FakeChannel,
    FakeGuild,
    FakeMember,
    FakeUser,
    embed_dict,
    forbidden,
)
from plugin_fakes import dispatch, golden
from xincord.core.bot import Bot
from xincord.plugins.welcome_goodbye.store import set_channel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord_fakes import Sent
    from xincord.core.storage import Store

GOLDEN = golden("welcome_goodbye")
AVATAR = FakeAsset("https://cdn.example/alice.png")


def make_guild(locale: str = "en-US", *, refused: bool = False) -> FakeGuild:
    """Guild 10 with 42 members, an icon and the text channels welcome (5), rules (6) and bye (7).

    It also has an announcement channel (8). With ``refused``, the welcome and bye channels refuse
    messages, as Discord does when the bot lacks a permission there.
    """
    error = forbidden() if refused else None
    rules = FakeChannel(id=6, name="rules")
    channels = [
        FakeChannel(id=5, name="welcome", error=error),
        rules,
        FakeChannel(id=7, name="bye", error=error),
        FakeChannel(id=8, name="news", type=discord.ChannelType.news),
    ]
    return FakeGuild(
        10,
        "guild",
        channels=channels,
        member_count=42,
        icon=FakeAsset("https://cdn.example/icon.png"),
        rules_channel=rules,
        preferred_locale=discord.Locale(locale),
    )


def alice(guild: FakeGuild, *, bot: bool = False) -> FakeMember:
    """alice, whose global name is Alice."""
    return FakeMember(guild, id=1, name="alice", bot=bot, global_name="Alice", avatar=AVATAR)


def messages(guild: FakeGuild) -> list[Sent]:
    """Every message the guild's channels received."""
    return [message for channel in guild.channels for message in channel.sent]


def embeds(guild: FakeGuild, channel_id: int) -> list[dict[str, Any]]:
    """The embeds of the one message that channel ``channel_id`` received."""
    channel = guild.get_channel(channel_id)
    assert channel is not None
    ((method, fields),) = channel.sent
    assert method == "channel.send"
    assert fields["content"] is None
    assert fields["view"] is None
    assert fields["files"] == ()
    return [embed_dict(embed) for embed in cast("Sequence[discord.Embed]", fields["embeds"])]


def removal(user: FakeUser | FakeMember, guild_id: int = 10) -> discord.RawMemberRemoveEvent:
    """The raw event of ``user`` leaving, being kicked or banned from guild ``guild_id``."""
    return cast("discord.RawMemberRemoveEvent", SimpleNamespace(guild_id=guild_id, user=user))


def know(bot: Bot, monkeypatch: pytest.MonkeyPatch, *guilds: FakeGuild) -> None:
    """Make ``guilds`` the bot's guilds, and BOT_USER its user, as after a login."""
    found = {guild.id: guild for guild in guilds}
    monkeypatch.setattr(bot, "get_guild", found.get)
    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_welcome(bot: Bot, store: Store, locale: str) -> None:
    """Requirement: Members who join are welcomed."""
    guild = make_guild(locale)
    await set_channel(store, 10, "welcome", 5)
    await set_channel(store, 10, "bye", 7)

    await dispatch(bot, "member_join", alice(guild).as_member())

    assert embeds(guild, 5) == [GOLDEN["welcome"][locale]]
    assert len(messages(guild)) == 1


async def test_other_locale(bot: Bot, store: Store) -> None:
    """Requirement: Members who join are welcomed."""
    guild = make_guild("ja")
    await set_channel(store, 10, "welcome", 5)

    await dispatch(bot, "member_join", alice(guild).as_member())

    assert embeds(guild, 5) == [GOLDEN["welcome"]["zh-TW"]]


async def test_bots_are_welcomed(bot: Bot, store: Store) -> None:
    """Requirement: Members who join are welcomed."""
    guild = make_guild()
    await set_channel(store, 10, "welcome", 5)

    await dispatch(bot, "member_join", alice(guild, bot=True).as_member())

    assert embeds(guild, 5) == [GOLDEN["welcome"]["en-US"]]


async def test_nothing_bound(bot: Bot, store: Store) -> None:
    """Requirement: Members who join are welcomed."""
    guild = make_guild()
    await set_channel(store, 10, "bye", 7)

    await dispatch(bot, "member_join", alice(guild).as_member())

    assert messages(guild) == []


@pytest.mark.parametrize("channel_id", [9, 8])  # deleted, then an announcement channel
async def test_channel_gone_or_not_a_text_channel(bot: Bot, store: Store, channel_id: int) -> None:
    """Requirement: Members who join are welcomed."""
    guild = make_guild()
    await set_channel(store, 10, "welcome", channel_id)

    await dispatch(bot, "member_join", alice(guild).as_member())

    assert messages(guild) == []


async def test_welcome_refused(bot: Bot, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Members who join are welcomed."""
    guild = make_guild(refused=True)
    await set_channel(store, 10, "welcome", 5)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "member_join", alice(guild).as_member())

    assert "WelcomeGoodbye cannot post the welcome message in welcome (5) of guild (10)" in (
        caplog.text
    )


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_bye(bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch, locale: str) -> None:
    """Requirement: Members who leave are seen off."""
    guild = make_guild(locale)
    know(bot, monkeypatch, guild)
    await set_channel(store, 10, "welcome", 5)
    await set_channel(store, 10, "bye", 7)

    await dispatch(bot, "raw_member_remove", removal(alice(guild)))

    assert embeds(guild, 7) == [GOLDEN["bye"][locale]]
    assert len(messages(guild)) == 1


async def test_uncached_user(bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Members who leave are seen off."""
    guild = make_guild()
    know(bot, monkeypatch, guild)
    await set_channel(store, 10, "bye", 7)
    user = FakeUser(id=1, name="alice", global_name="Alice", avatar=AVATAR)

    await dispatch(bot, "raw_member_remove", removal(user))

    assert embeds(guild, 7) == [GOLDEN["bye"]["en-US"]]


async def test_bot_removed(bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Members who leave are seen off."""
    guild = make_guild()
    know(bot, monkeypatch, guild)
    await set_channel(store, 10, "bye", 7)

    await dispatch(bot, "raw_member_remove", removal(BOT_USER))

    assert messages(guild) == []


@pytest.mark.parametrize("guild_id", [10, 20])  # without a bye channel, then unknown
async def test_nothing_to_send(
    bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch, guild_id: int
) -> None:
    """Requirement: Members who leave are seen off."""
    guild = make_guild()
    know(bot, monkeypatch, guild)
    await set_channel(store, 10, "welcome", 5)
    await set_channel(store, 20, "bye", 7)

    await dispatch(bot, "raw_member_remove", removal(alice(guild), guild_id))

    assert messages(guild) == []


async def test_bye_refused(
    bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Members who leave are seen off."""
    guild = make_guild(refused=True)
    know(bot, monkeypatch, guild)
    await set_channel(store, 10, "bye", 7)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "raw_member_remove", removal(alice(guild)))

    assert "WelcomeGoodbye cannot post the bye message in bye (7) of guild (10)" in caplog.text
