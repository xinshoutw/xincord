"""The guild and member counts that /bot-info shows.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/BotInfo.kt:24-27
"""

import pytest

from discord_fakes import FakeGuild
from xincord.plugins.bot_info.cog import counts

XFAIL = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The counts sum the bot's guilds"
)


@XFAIL
def test_guilds_and_members() -> None:
    """Requirement: The counts sum the bot's guilds."""
    guilds = [FakeGuild(10, member_count=3), FakeGuild(20, member_count=4)]

    assert counts(guilds) == (2, 7)


@XFAIL
def test_unknown_member_count() -> None:
    """Requirement: The counts sum the bot's guilds."""
    guilds = [FakeGuild(10, member_count=5), FakeGuild(20, unavailable=True)]

    assert counts(guilds) == (2, 5)


@XFAIL
def test_no_guilds() -> None:
    """Requirement: The counts sum the bot's guilds."""
    assert counts([]) == (0, 0)
