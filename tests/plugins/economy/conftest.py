"""Fixtures for the Economy tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.economy.cog import Economy

# An operator's config.yaml: the administrator 1 and a board of three rows.
CONFIG = "admin_id: [1]\nboard_user_show_limit: 3\n"


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded Economy from `tmp_path / "plugins"` and never connects.

    The plugin's wallets are in ``store``, the same store as the tests'.
    """
    return await load_plugin("Economy", tmp_path / "plugins", store, config=CONFIG)


@pytest.fixture
def cog(bot: Bot) -> Economy:
    """The loaded plugin's cog.

    No isinstance check: test_config.py loads invalid files, after which discord.py imports the
    plugin's modules again, so the class differs from one imported when the tests were collected.
    """
    found = bot.get_cog("Economy")
    assert found is not None
    return cast("Economy", found)
