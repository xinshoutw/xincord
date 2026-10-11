"""The BotInfo plugin's entry point, intents and bundled files."""

from importlib.resources import files
from typing import TYPE_CHECKING

import discord

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

LANG_FILES = (
    "en-US/register.yaml",
    "en-US/message/bot-info.yaml",
    "zh-TW/register.yaml",
    "zh-TW/message/bot-info.yaml",
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as BotInfo."""
    assert discover(["BotInfo"]) == [
        PluginInfo("BotInfo", "xincord.plugins.bot_info", intents=discord.Intents(members=True))
    ]


async def test_the_bot_requests_the_members_intent(bot: Bot) -> None:
    """Requirement: The plugin installs as BotInfo."""
    assert bot.loaded == ("BotInfo",)
    assert bot.intents.members


async def test_first_load_creates_the_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as BotInfo."""
    directory = tmp_path / "plugins" / "BotInfo"

    assert bot.loaded == ("BotInfo",)
    bundled = files("xincord.plugins.bot_info").joinpath("config.yaml")
    assert (directory / "config.yaml").read_text(encoding="utf-8") == bundled.read_text(
        encoding="utf-8"
    )
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
