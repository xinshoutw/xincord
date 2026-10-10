"""Fixtures for the VoiceLogger tests: the plugin loads through its real entry point.

Discord's REST requests are recorded instead of sent, and the bot has its user, as after a login.
"""

from typing import TYPE_CHECKING, cast

import pytest

from discord_fakes import BOT_USER, FakeChannel, FakeRest
from plugin_fakes import load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.voice_logger.cog import VoiceLogger


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


@pytest.fixture
def cog(bot: Bot) -> VoiceLogger:
    """The loaded plugin's cog.

    No isinstance check: a load that fails, as into a ready bot whose check raises, makes
    discord.py import the plugin's modules again, so the class differs from the one imported
    when the tests were collected.
    """
    found = bot.get_cog("VoiceLogger")
    assert found is not None
    return cast("VoiceLogger", found)


@pytest.fixture
def channels(bot: Bot, monkeypatch: pytest.MonkeyPatch) -> dict[int, FakeChannel]:
    """The listen channels that the plugin posts to, by ID; each is created at its first use.

    The plugin reaches them through ``bot.get_partial_messageable``, which needs no cache. Put a
    channel here before the post to make it fail (``FakeChannel(id=..., error=...)``).
    """
    created: dict[int, FakeChannel] = {}

    def partial(channel_id: int, *, guild_id: int | None = None) -> FakeChannel:
        assert guild_id is not None  # the listen channel's guild
        return created.setdefault(channel_id, FakeChannel(id=channel_id))

    monkeypatch.setattr(bot, "get_partial_messageable", partial)
    return created
