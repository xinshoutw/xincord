"""Members who join a configured guild get its roles.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/AutoRole.kt:21-25
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/Event.kt:28-31
"""

from typing import TYPE_CHECKING

from discord_fakes import FakeGuild, FakeMember, FakeRole
from plugin_fakes import dispatch, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store

# One add_roles call per role, atomic: discord.py's add-role request, which keeps other roles.
EACH_ROLE = [((11,), True), ((12,), True)]


async def test_join_in_a_configured_guild(bot: Bot, guild: FakeGuild) -> None:
    """Requirement: Members who join get the guild's roles."""
    member = FakeMember(guild)

    await dispatch(bot, "member_join", member.as_member())

    assert member.requests == EACH_ROLE


async def test_bot_joins(bot: Bot, guild: FakeGuild) -> None:
    """Requirement: Members who join get the guild's roles."""
    member = FakeMember(guild, id=2, name="helper", bot=True)

    await dispatch(bot, "member_join", member.as_member())

    assert member.requests == EACH_ROLE


async def test_role_listed_twice(store: Store, tmp_path: Path, guild: FakeGuild) -> None:
    """Requirement: Members who join get the guild's roles."""
    config = "guilds:\n  - guild_id: 10\n    role_ids: [11, 12, 11]\n"
    bot = await load_plugin("AutoRole", tmp_path / "plugins", store, config=config)
    member = FakeMember(guild)

    await dispatch(bot, "member_join", member.as_member())

    assert member.requests == EACH_ROLE


async def test_join_in_another_guild(bot: Bot) -> None:
    """Requirement: Members who join get the guild's roles."""
    member = FakeMember(FakeGuild(30, "other", [FakeRole(11), FakeRole(12)]))

    await dispatch(bot, "member_join", member.as_member())

    assert member.requests == []
