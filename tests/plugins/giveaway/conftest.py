"""Fixtures for the Giveaway tests: the plugin loads through its real entry point.

The bot has its user, as after a login, and READY waits for the tests, as the plugin's automatic
draw waits for it.
"""

from typing import TYPE_CHECKING, cast

import pytest

from discord_fakes import BOT_USER
from plugin_fakes import Ready, load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.giveaway.cog import Giveaway


@pytest.fixture(autouse=True)
def logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bot's user, which discord.py sets at the login, for v3's ``bot_*`` values."""
    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loops wait for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@pytest.fixture
def config() -> str | None:
    """The operator's ``config.yaml``, or None for the bundled one; tests parametrize it."""
    return None


@pytest.fixture
async def bot(store: Store, tmp_path: Path, config: str | None) -> Bot:
    """A bot that loaded Giveaway from `tmp_path / "plugins"` and never connects.

    The plugin's giveaways are in ``store``, the same store as the tests'.
    """
    return await load_plugin("Giveaway", tmp_path / "plugins", store, config=config)


@pytest.fixture
def cog(bot: Bot) -> Giveaway:
    """The loaded plugin's cog.

    No isinstance check: test_config.py loads invalid files, after which discord.py imports the
    plugin's modules again, so the class differs from the one imported when the tests were
    collected.
    """
    found = bot.get_cog("Giveaway")
    assert found is not None
    return cast("Giveaway", found)
