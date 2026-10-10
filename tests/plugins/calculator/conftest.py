"""Fixtures for the Calculator tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.plugins.calculator.cog import Calculator

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded Calculator from `tmp_path / "plugins"` and never connects."""
    return await load_plugin("Calculator", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> Calculator:
    """The loaded plugin's cog."""
    found = bot.get_cog("Calculator")
    assert isinstance(found, Calculator)
    return found
