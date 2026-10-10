"""Fixtures for the NtustAnnouncements tests: the plugin loads through its real entry point.

READY never comes unless a test sets it, so the boards' loops wait for it; the loops left running
are cancelled when the test ends.
"""

import sys
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import Ready

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

PACKAGE = "xincord.plugins.ntust_announcements"


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


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loops wait for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()
