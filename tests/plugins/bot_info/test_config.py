"""The BotInfo config: the source link of decision C3.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/config/ConfigSerializer.kt:5-8
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/config.yaml:1
"""

import logging
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.bot_info.cog import BotInfo

DEFAULT_URL = "https://github.com/xinshoutw/xincord"
HOST = "https://git.example/"  # 20 characters


def loaded_cog(bot: Bot) -> BotInfo:
    """The cog of the loaded plugin.

    When a plugin's setup fails, as with the invalid files below, discord.py drops its modules, and
    the next load imports them again: an isinstance check against the class imported here would
    depend on the test order.
    """
    cog = bot.get_cog("BotInfo")
    assert cog is not None
    return cast("BotInfo", cog)


async def test_default_config(tmp_path: Path, store: Store) -> None:
    """Requirement: The config sets the source link."""
    bot = await load_plugin("BotInfo", tmp_path / "plugins", store)

    assert loaded_cog(bot).config.source_url == DEFAULT_URL


async def test_v3_config_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config sets the source link."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("BotInfo", tmp_path / "plugins", store, config="enabled: true\n")

    assert "unknown key enabled" in caplog.text
    assert loaded_cog(bot).config.source_url == DEFAULT_URL


@pytest.mark.parametrize("url", [f"{HOST}bot", "http://git.example/bot", HOST + "a" * 492])
async def test_operator_url(url: str, tmp_path: Path, store: Store) -> None:
    """Requirement: The config sets the source link."""
    config = f'source_url: "{url}"\n'
    bot = await load_plugin("BotInfo", tmp_path / "plugins", store, config=config)

    assert loaded_cog(bot).config.source_url == url


@pytest.mark.parametrize(
    "url", ["", "git.example/bot", "ftp://git.example/bot", f"{HOST}my bot", HOST + "a" * 493]
)
async def test_invalid_url(
    url: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config sets the source link."""
    config = f'source_url: "{url}"\n'
    bot = await load_plugin("BotInfo", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert "source_url: String should" in caplog.text
