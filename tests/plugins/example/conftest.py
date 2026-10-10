"""Fixtures for the Example tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.plugins.example.cog import Example

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded Example from `tmp_path / "plugins"` and never connects."""
    return await load_plugin("Example", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> Example:
    """The loaded plugin's cog."""
    found = bot.get_cog("Example")
    assert isinstance(found, Example)
    return found
