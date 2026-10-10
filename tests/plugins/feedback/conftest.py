"""Fixtures for the Feedback tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.feedback.cog import Feedback


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded Feedback from `tmp_path / "plugins"` and never connects."""
    return await load_plugin("Feedback", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> Feedback:
    """The loaded plugin's cog.

    No isinstance check: test_config.py loads invalid files, after which discord.py imports the
    plugin's modules again, so the class differs from one imported when the tests were collected.
    """
    found = bot.get_cog("Feedback")
    assert found is not None
    return cast("Feedback", found)
