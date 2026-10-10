"""The guild and member counts that /bot-info shows.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/BotInfo.kt:24-27
"""

from discord_fakes import FakeGuild
from xincord.plugins.bot_info.cog import counts


def test_guilds_and_members() -> None:
    """Requirement: The counts sum the bot's guilds."""
    guilds = [FakeGuild(10, member_count=3), FakeGuild(20, member_count=4)]

    assert counts(guilds) == (2, 7)


def test_unknown_member_count() -> None:
    """Requirement: The counts sum the bot's guilds."""
    guilds = [FakeGuild(10, member_count=5), FakeGuild(20, unavailable=True)]

    assert counts(guilds) == (2, 5)


def test_no_guilds() -> None:
    """Requirement: The counts sum the bot's guilds."""
    assert counts([]) == (0, 0)
