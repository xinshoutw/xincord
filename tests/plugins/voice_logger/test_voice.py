"""Voice joins, leaves and switches, posted to the listen channels that detect them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/Event.kt:106-109
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:144-161
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:278-364
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/message/on-channel-join.yaml:1-18
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/message/on-channel-switch.yaml:1-24
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeMember, FakeVoiceChannel, embed_dict, voice_state
from plugin_fakes import dispatch, golden
from xincord.plugins.voice_logger.store import add_channels, toggle

if TYPE_CHECKING:
    from discord_fakes import FakeChannel
    from xincord.core.bot import Bot
    from xincord.core.storage import Store

GOLDEN = golden("voice_logger")
XFAIL = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Voice channel changes are logged"
)
LOCALES = {"en-US": discord.Locale.american_english, "zh-TW": discord.Locale.taiwan_chinese}


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


@XFAIL
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
@pytest.mark.parametrize("who", ["member", "bot"])
async def test_join(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], locale: str, who: str
) -> None:
    """Requirement: Voice channel changes are logged."""
    await add_channels(store, 10, 5, "allow", [20])  # the category of Room A
    guild = voice_guild(LOCALES[locale])
    member = FakeMember(guild, id=7, bot=who == "bot")  # bots are logged too, as in v3

    await move(bot, member, None, room(guild, 30))

    assert posts(channels[5]) == [GOLDEN["voice"][locale]["join"]]


@XFAIL
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_leave_without_a_category(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], locale: str
) -> None:
    """Requirement: Voice channel changes are logged."""
    await toggle(store, 10, 5)  # the block mode, nothing blocked: every channel
    guild = voice_guild(LOCALES[locale])

    await move(bot, FakeMember(guild, id=7), room(guild, 33), None)

    # v3 left the category key unset: an earlier event's category, or the placeholder itself.
    assert posts(channels[5]) == [GOLDEN["voice"][locale]["left"]]


@XFAIL
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_switch(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], locale: str
) -> None:
    """Requirement: Voice channel changes are logged."""
    await add_channels(store, 10, 5, "allow", [30])
    await add_channels(store, 10, 6, "allow", [32])
    await add_channels(store, 10, 7, "allow", [33])
    guild = voice_guild(LOCALES[locale])

    await move(bot, FakeMember(guild, id=7), room(guild, 30), room(guild, 32))

    # v3 never set the joined channel's mention for a switch.
    expected = GOLDEN["voice"][locale]["switch"]
    assert posts(channels[5]) == posts(channels[6]) == [expected]
    assert 7 not in channels  # it detects neither side


@XFAIL
async def test_same_channel(bot: Bot, store: Store, channels: dict[int, FakeChannel]) -> None:
    """Requirement: Voice channel changes are logged."""
    await toggle(store, 10, 5)
    guild = voice_guild()
    room_a = room(guild, 30)
    # discord.py's before is a copy of the voice state, with an equal channel.
    copy = FakeVoiceChannel(id=30, name="Room A", guild=guild, category_id=20)

    await move(bot, FakeMember(guild, id=7), room_a, room_a)  # a mute or a deafen
    await move(bot, FakeMember(guild, id=7), copy, room_a)  # a stream

    assert channels == {}


@XFAIL
async def test_not_detected(bot: Bot, store: Store, channels: dict[int, FakeChannel]) -> None:
    """Requirement: Voice channel changes are logged."""
    guild = voice_guild()
    await move(bot, FakeMember(guild, id=7), None, room(guild, 30))  # no settings at all
    await add_channels(store, 10, 5, "allow", [99])

    await move(bot, FakeMember(guild, id=7), None, room(guild, 30))

    assert channels == {}
