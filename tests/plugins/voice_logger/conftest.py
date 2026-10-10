"""Fixtures for the VoiceLogger tests: the plugin loads through its real entry point.

Discord's REST requests are recorded instead of sent, and the bot has its user, as after a login.
"""

from typing import TYPE_CHECKING

import pytest

from discord_fakes import BOT_USER, FakeRest
from plugin_fakes import load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store


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


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded VoiceLogger from `tmp_path / "plugins"` and never connects.

    The plugin's settings are in ``store``, the same store as the tests'.
    """
    return await load_plugin("VoiceLogger", tmp_path / "plugins", store)
