"""Fixtures for the Feedbacker tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.feedbacker.cog import Feedbacker


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded Feedbacker from `tmp_path / "plugins"` and never connects."""
    return await load_plugin("Feedbacker", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> Feedbacker:
    """The loaded plugin's cog.

    No isinstance check: test_config.py loads invalid files, after which discord.py imports the
    plugin's modules again, so the class differs from one imported when the tests were collected.
    """
    found = bot.get_cog("Feedbacker")
    assert found is not None
    return cast("Feedbacker", found)
