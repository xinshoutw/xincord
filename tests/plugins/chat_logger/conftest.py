"""Fixtures for the ChatLogger tests: the plugin loads through its real entry point.

Discord's REST requests are recorded instead of sent, the bot has its user, as after a login, and
READY waits for the tests, as the plugin's retention loop waits for it.
"""

from typing import TYPE_CHECKING, cast

import pytest

from discord_fakes import BOT_USER, FakeRest
from plugin_fakes import Ready, load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.chat_logger.cog import ChatLogger


@pytest.fixture(autouse=True)
def rest(monkeypatch: pytest.MonkeyPatch) -> FakeRest:
    """Discord's REST requests, recorded instead of sent; each answers at once."""
    recorded = FakeRest()
    recorded.install(monkeypatch)
    return recorded


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
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded ChatLogger from `tmp_path / "plugins"` and never connects.

    The plugin's settings and messages are in ``store``, the same store as the tests'.
    """
    return await load_plugin("ChatLogger", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> ChatLogger:
    """The loaded plugin's cog.

    No isinstance check: a load that fails, as with an invalid config, makes discord.py import the
    plugin's modules again, so the class differs from the one imported when the tests were
    collected.
    """
    found = bot.get_cog("ChatLogger")
    assert found is not None
    return cast("ChatLogger", found)
