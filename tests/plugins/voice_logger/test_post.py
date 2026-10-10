"""Each log reaches every listen channel that detects it, in the guild's locale.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:352-364
"""

import logging
from typing import TYPE_CHECKING, cast

import discord

from discord_fakes import (
    FakeChannel,
    FakeGuild,
    FakeMember,
    FakeVoiceChannel,
    forbidden,
    not_found,
    voice_state,
)
from plugin_fakes import dispatch, golden
from xincord.plugins.voice_logger.settings import Setting
from xincord.plugins.voice_logger.store import add_channels, read_settings

if TYPE_CHECKING:
    import pytest

    from xincord.core.bot import Bot
    from xincord.core.storage import Store

GOLDEN = golden("voice_logger")


async def join(bot: Bot, locale: discord.Locale = discord.Locale.american_english) -> None:
    """Member 7 joins Room A (30, category 20) of guild 10, whose locale is ``locale``."""
    guild = FakeGuild(10, "guild", preferred_locale=locale)
    room = FakeVoiceChannel(id=30, name="Room A", guild=guild, category_id=20)
    guild.channels = [room]
    member = FakeMember(guild, id=7).as_member()
    await dispatch(bot, "voice_state_update", member, voice_state(None), voice_state(room))


def titles(channel: FakeChannel) -> list[str]:
    """The titles of the embeds that ``channel`` received."""
    found: list[str] = []
    for _, fields in channel.sent:
        [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
        found.append(str(embed.title))
    return found


async def test_locale_without_templates(
    bot: Bot, store: Store, channels: dict[int, FakeChannel]
) -> None:
    """Requirement: Logs reach every listen channel."""
    await add_channels(store, 10, 5, "allow", [30])

    await join(bot, discord.Locale.french)

    assert titles(channels[5]) == [GOLDEN["voice"]["zh-TW"]["join"]["title"]]  # v3's default


async def test_deleted_listen_channel(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Logs reach every listen channel."""
    await add_channels(store, 10, 5, "allow", [30])
    await add_channels(store, 10, 6, "allow", [30])
    channels[5] = FakeChannel(id=5, error=not_found())
    caplog.set_level(logging.INFO)

    await join(bot)

    # v3 returned at the first listen channel it did not find, skipping the others.
    assert await read_settings(store, 10) == {6: Setting(allow=(30,))}
    assert "VoiceLogger forgot the listen channel 5 of guild (10)" in caplog.text
    assert titles(channels[6]) == [GOLDEN["voice"]["en-US"]["join"]["title"]]


async def test_refused_listen_channel(
    bot: Bot, store: Store, channels: dict[int, FakeChannel], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Logs reach every listen channel."""
    await add_channels(store, 10, 5, "allow", [30])
    await add_channels(store, 10, 6, "allow", [30])
    channels[5] = FakeChannel(id=5, error=forbidden())

    await join(bot)

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert [record.getMessage() for record in warnings] == [
        (
            "VoiceLogger cannot post in the listen channel 5 of guild (10): "
            "403 Forbidden (error code: 0): Missing Permissions"
        )
    ]
    assert sorted(await read_settings(store, 10)) == [5, 6]
    assert titles(channels[6]) == [GOLDEN["voice"]["en-US"]["join"]["title"]]
