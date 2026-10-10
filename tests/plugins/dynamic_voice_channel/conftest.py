"""Fixtures for the DynamicVoiceChannel tests: the plugin loads through its real entry point."""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.plugins.dynamic_voice_channel.cog import DynamicVoiceChannel

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded DynamicVoiceChannel from `tmp_path / "plugins"` and never connects.

    The plugin's bindings and rooms are in ``store``, the same store as the tests'.
    """
    return await load_plugin("DynamicVoiceChannel", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> DynamicVoiceChannel:
    """The loaded plugin's cog."""
    found = bot.get_cog("DynamicVoiceChannel")
    assert isinstance(found, DynamicVoiceChannel)
    return found
