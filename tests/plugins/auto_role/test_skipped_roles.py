"""Roles that the bot cannot give are skipped with a warning, and the others are given.

Kotlin (v3 gave no role at all in these cases, or dropped unknown IDs without a log):
"""

import logging
from typing import TYPE_CHECKING

import discord

from discord_fakes import FakeGuild, FakeMember, FakeRole, forbidden
from plugin_fakes import dispatch, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


async def test_missing_role(bot: Bot, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Roles that cannot be given are skipped."""
    member = FakeMember(FakeGuild(10, "guild", [FakeRole(11, "member")]))

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "member_join", member.as_member())

    assert member.requests == [((11,), True)]
    assert "AutoRole skips role 12: it is not in guild (10)" in caplog.text


async def test_role_of_another_guild(
    store: Store, tmp_path: Path, guild: FakeGuild, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Roles that cannot be given are skipped."""
    # Role 21 is guild 20's: v3 found it in any guild, and JDA then refused every role.
    config = "guilds:\n  - guild_id: 10\n    role_ids: [11, 21]\n"
    bot = await load_plugin("AutoRole", tmp_path / "plugins", store, config=config)
    member = FakeMember(guild)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "member_join", member.as_member())

    assert member.requests == [((11,), True)]
    assert "AutoRole skips role 21: it is not in guild (10)" in caplog.text


async def test_role_created_later(bot: Bot) -> None:
    """Requirement: Roles that cannot be given are skipped."""
    guild = FakeGuild(10, "guild", [FakeRole(11, "member")])
    first, second = FakeMember(guild), FakeMember(guild, id=2, name="bob")

    await dispatch(bot, "member_join", first.as_member())
    guild.roles.append(FakeRole(12, "news"))
    await dispatch(bot, "member_join", second.as_member())

    assert first.requests == [((11,), True)]
    assert second.requests == [((11,), True), ((12,), True)]


async def test_role_the_bot_cannot_give(bot: Bot, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Roles that cannot be given are skipped."""
    roles = [FakeRole(11, "member", assignable=False), FakeRole(12, "news")]
    member = FakeMember(FakeGuild(10, "guild", roles))

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "member_join", member.as_member())

    assert member.requests == [((12,), True)]
    assert (
        "AutoRole skips role member (11) in guild (10): it is managed, @everyone or not below "
        "the bot's highest role"
    ) in caplog.text


async def test_missing_manage_roles(
    bot: Bot, guild: FakeGuild, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Roles that cannot be given are skipped."""
    guild.permissions = discord.Permissions.none()
    member = FakeMember(guild)

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "member_join", member.as_member())

    assert member.requests == []
    assert "AutoRole gives no roles in guild (10): the bot lacks Manage Roles" in caplog.text


async def test_failed_request(bot: Bot, guild: FakeGuild, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Roles that cannot be given are skipped."""
    member = FakeMember(guild, errors={11: forbidden()})

    with caplog.at_level(logging.WARNING):
        await dispatch(bot, "member_join", member.as_member())

    assert member.requests == [((12,), True)]
    assert (
        "AutoRole could not give role member (11) to alice (1) in guild (10): 403 Forbidden"
    ) in caplog.text
