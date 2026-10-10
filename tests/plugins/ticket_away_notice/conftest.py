"""Fixtures for the TicketAwayNotice tests: the plugin loads through its real entry point."""

import sys
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store

PACKAGE = "xincord.plugins.ticket_away_notice"
GUILD = 10  # the watched guild
OWNER = 20  # the member whose status decides the notice
# Guild 10 and owner 20, two ASCII prefixes and v3's 2 seconds; the bundled file waits for IDs.
CONFIG = """\
guild_id: 10
user_id: 20
prefix:
  - "ticket-"
  - "order-"
delay_millis: 2000
"""


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py drops a plugin's modules when its setup fails (an invalid config), and the next load
    imports new ones, whose classes differ from those that the test modules imported.
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
    """A bot that loaded TicketAwayNotice with `CONFIG` from `tmp_path / "plugins"`, offline."""
    return await load_plugin("TicketAwayNotice", tmp_path / "plugins", store, config=CONFIG)
