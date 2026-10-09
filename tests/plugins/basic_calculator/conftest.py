"""Fixtures for the BasicCalculator tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded BasicCalculator from `tmp_path / "plugins"` and never connects."""
    return await load_plugin("BasicCalculator", tmp_path / "plugins", store)
