"""Fixtures for the CustomCommands tests: the plugin loads through its real entry point."""

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.plugins.custom_commands.cog import CustomCommands

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store

PACKAGE = "xincord.plugins.custom_commands"


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py imports a plugin's modules again when it reloads the plugin or when a load fails
    (an invalid config), and the classes of the new modules fail isinstance checks against those
    that the test modules imported.
    """
    kept = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(f"{PACKAGE}.")
    }
    yield
    sys.modules.update(kept)


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


@dataclass
class Operator:
    """Writes the operator's files under ``root``, which stands for ``plugins/``, and loads."""

    root: Path
    store: Store

    @property
    def directory(self) -> Path:
        """The plugin's directory, ``plugins/CustomCommands``."""
        return self.root / "CustomCommands"

    def template(self, name: str, text: str, locale: str = "zh-TW") -> Path:
        """Write the message template ``name`` in ``locale``; return its file."""
        path = self.directory / "lang" / locale / "message" / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    async def load(self, config: str | None = None) -> Bot:
        """Load the plugin with ``config`` as its ``config.yaml``, or the bundled one."""
        return await load_plugin("CustomCommands", self.root, self.store, config=config)


@pytest.fixture
def operator(store: Store, tmp_path: Path) -> Operator:
    """The operator of a bot in `tmp_path`, whose plugin loads when the test says so."""
    return Operator(tmp_path / "plugins", store)
