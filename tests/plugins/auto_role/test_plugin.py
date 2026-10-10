"""The AutoRole plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/Event.kt:7-15
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:68-72
"""

from importlib.resources import files
from typing import TYPE_CHECKING

import discord

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as AutoRole."""
    assert discover(["AutoRole"]) == [
        PluginInfo("AutoRole", "xincord.plugins.auto_role", intents=discord.Intents(members=True))
    ]


async def test_the_bot_requests_the_members_intent(bot: Bot) -> None:
    """Requirement: The plugin installs as AutoRole."""
    assert bot.loaded == ("AutoRole",)
    assert bot.intents.members


async def test_first_load_creates_the_config(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as AutoRole."""
    bot = await load_plugin("AutoRole", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "AutoRole"

    assert bot.loaded == ("AutoRole",)
    bundled = files("xincord.plugins.auto_role").joinpath("config.yaml")
    assert (directory / "config.yaml").read_text(encoding="utf-8") == bundled.read_text(
        encoding="utf-8"
    )
    assert not (directory / "lang").exists()  # v3 had no text
