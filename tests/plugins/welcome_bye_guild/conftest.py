"""Fixtures for the WelcomeByeGuild tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.plugins.welcome_bye_guild.cog import WelcomeByeGuild

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded WelcomeByeGuild from `tmp_path / "plugins"` and never connects."""
    return await load_plugin("WelcomeByeGuild", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> WelcomeByeGuild:
    """The loaded plugin's cog."""
    found = bot.get_cog("WelcomeByeGuild")
    assert isinstance(found, WelcomeByeGuild)
    return found
