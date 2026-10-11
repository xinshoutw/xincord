"""Voice joins, leaves and switches, posted to the listen channels that detect them."""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeMember, FakeVoiceChannel, embed_dict, voice_state
from plugin_fakes import dispatch, golden
from xincord.plugins.listen_channels.store import ListenSettings
from xincord.plugins.voice_logger.cog import NAMESPACE

if TYPE_CHECKING:
    from discord_fakes import FakeChannel
    from xincord.core.bot import Bot
    from xincord.core.storage import Store

GOLDEN = golden("voice_logger")
LOCALES = {"en-US": discord.Locale.american_english, "zh-TW": discord.Locale.taiwan_chinese}


def settings(store: Store) -> ListenSettings:
    """VoiceLogger's listen channel settings in ``store``."""
    return ListenSettings(store, NAMESPACE)


def voice_guild(locale: discord.Locale = LOCALES["en-US"]) -> FakeGuild:
    """Guild 10 with Room A (30, category 20), Room B (32, category 21) and Loose (33)."""
    guild = FakeGuild(10, "guild", preferred_locale=locale)
    guild.channels = [
        FakeVoiceChannel(id=30, name="Room A", guild=guild, category_id=20),
        FakeVoiceChannel(id=32, name="Room B", guild=guild, category_id=21),
        FakeVoiceChannel(id=33, name="Loose", guild=guild, category_id=None),
    ]
    return guild


def room(guild: FakeGuild, channel_id: int) -> FakeVoiceChannel:
    """The voice channel ``channel_id`` of ``guild``."""
    channel = guild.get_channel(channel_id)
    assert isinstance(channel, FakeVoiceChannel)
    return channel


async def move(
    bot: Bot, member: FakeMember, before: FakeVoiceChannel | None, after: FakeVoiceChannel | None
) -> None:
    """``member`` moves from ``before`` to ``after`` (None: outside voice channels)."""
    await dispatch(
        bot, "voice_state_update", member.as_member(), voice_state(before), voice_state(after)
    )


def posts(channel: FakeChannel) -> list[dict[str, Any]]:
    """The embeds that ``channel`` received, one per message."""
    found: list[dict[str, Any]] = []
    for method, fields in channel.sent:
        assert method == "channel.send"
        [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
        found.append(embed_dict(embed))
    return found


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
@pytest.mark.parametrize("who", ["member", "bot"])
async def test_join(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], locale: str, who: str
) -> None:
    """Requirement: Voice channel changes are logged."""
    await settings(store).add_channels(10, 5, "allow", [20])  # the category of Room A
    guild = voice_guild(LOCALES[locale])
    member = FakeMember(guild, id=7, bot=who == "bot")  # bots are logged too

    await move(bot, member, None, room(guild, 30))

    assert posts(channels[5]) == [GOLDEN["voice"][locale]["join"]]


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_leave_without_a_category(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], locale: str
) -> None:
    """Requirement: Voice channel changes are logged."""
    await settings(store).toggle(10, 5)  # the block mode, nothing blocked: every channel
    guild = voice_guild(LOCALES[locale])

    await move(bot, FakeMember(guild, id=7), room(guild, 33), None)

    # Outside categories, the category shows -.
    assert posts(channels[5]) == [GOLDEN["voice"][locale]["left"]]


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_switch(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], locale: str
) -> None:
    """Requirement: Voice channel changes are logged."""
    await settings(store).add_channels(10, 5, "allow", [30])
    await settings(store).add_channels(10, 6, "allow", [32])
    await settings(store).add_channels(10, 7, "allow", [33])
    guild = voice_guild(LOCALES[locale])

    await move(bot, FakeMember(guild, id=7), room(guild, 30), room(guild, 32))

    # A switch has both channels' mentions.
    expected = GOLDEN["voice"][locale]["switch"]
    assert posts(channels[5]) == posts(channels[6]) == [expected]
    assert 7 not in channels  # it detects neither side


async def test_same_channel(bot: Bot, store: Store, channels: dict[int, FakeChannel]) -> None:
    """Requirement: Voice channel changes are logged."""
    await settings(store).toggle(10, 5)
    guild = voice_guild()
    room_a = room(guild, 30)
    # discord.py's before is a copy of the voice state, with an equal channel.
    copy = FakeVoiceChannel(id=30, name="Room A", guild=guild, category_id=20)

    await move(bot, FakeMember(guild, id=7), room_a, room_a)  # a mute or a deafen
    await move(bot, FakeMember(guild, id=7), copy, room_a)  # a stream

    assert channels == {}


async def test_not_detected(bot: Bot, store: Store, channels: dict[int, FakeChannel]) -> None:
    """Requirement: Voice channel changes are logged."""
    guild = voice_guild()
    await move(bot, FakeMember(guild, id=7), None, room(guild, 30))  # no settings at all
    await settings(store).add_channels(10, 5, "allow", [99])

    await move(bot, FakeMember(guild, id=7), None, room(guild, 30))

    assert channels == {}
