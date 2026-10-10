"""Fixtures for the AutoRole tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING

import pytest

from discord_fakes import FakeGuild, FakeRole
from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store

# Guild 10 gives the roles 11 and 12, guild 20 the role 21.
CONFIG = """\
guilds:
  - guild_id: 10
    role_ids: [11, 12]
  - guild_id: 20
    role_ids: [21]
"""


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded AutoRole with `CONFIG` from `tmp_path / "plugins"`, never connecting."""
    return await load_plugin("AutoRole", tmp_path / "plugins", store, config=CONFIG)


@pytest.fixture
def guild() -> FakeGuild:
    """Guild 10 with the roles 11 and 12, both below the bot's, which has Manage Roles."""
    return FakeGuild(10, "guild", [FakeRole(11, "member"), FakeRole(12, "news")])
