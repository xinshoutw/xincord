"""Fixtures for the Ticket tests: the plugin loads through its real entry point.

The bot has its user, as after a login.
"""

import sys
from typing import TYPE_CHECKING, cast

import pytest

from discord_fakes import BOT_USER
from plugin_fakes import load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.ticket.cog import Ticket

PACKAGE = "xincord.plugins.ticket"


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py drops a plugin's modules when its setup fails, and the next load imports new ones,
    whose dataclasses never equal those that the test modules imported.
    """
    kept = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(f"{PACKAGE}.")
    }
    yield
    sys.modules.update(kept)


@pytest.fixture(autouse=True)
def logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bot's user, which discord.py sets at the login, for v3's ``bot_*`` values."""
    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded Ticket from `tmp_path / "plugins"` and never connects.

    The plugin's panels are in ``store``, the same store as the tests'.
    """
    return await load_plugin("Ticket", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> Ticket:
    """The loaded plugin's cog.

    No isinstance check: a failed load makes discord.py import the plugin's modules again, so the
    class may differ from the one imported when the tests were collected.
    """
    found = bot.get_cog("Ticket")
    assert found is not None
    return cast("Ticket", found)
