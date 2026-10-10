"""Fixtures for the CustomCommands tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.plugins.custom_commands.cog import CustomCommands

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded CustomCommands from `tmp_path / "plugins"` and never connects."""
    return await load_plugin("CustomCommands", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> CustomCommands:
    """The loaded plugin's cog."""
    found = bot.get_cog("CustomCommands")
    assert isinstance(found, CustomCommands)
    return found
