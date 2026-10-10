"""The CustomCommands plugin's entry point and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:14-30
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/config/ConfigSerializer.kt:5-8
"""

from importlib.resources import files
from typing import TYPE_CHECKING

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

TEMPLATES = (
    "zh-TW/message/cub-none-card.yaml",
    "zh-TW/message/tsib-none-card.yaml",
    "zh-TW/message/ctcb-none-card.yaml",
    "zh-TW/message/ctcb-remit.yaml",
    "zh-TW/message/chpytwtp-remit.yaml",
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as CustomCommands."""
    assert discover(["CustomCommands"]) == [
        PluginInfo("CustomCommands", "xincord.plugins.custom_commands")
    ]


async def test_first_load_creates_the_lang_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as CustomCommands."""
    directory = tmp_path / "plugins" / "CustomCommands"
    bundled = files("xincord.plugins.custom_commands").joinpath("config.yaml")

    assert bot.loaded == ("CustomCommands",)
    assert (directory / "config.yaml").read_text(encoding="utf-8") == bundled.read_text(
        encoding="utf-8"
    )
    for name in TEMPLATES:
        assert (directory / "lang" / name).is_file()
    # The commands' names and descriptions are in config.yaml.
    assert not (directory / "lang" / "zh-TW" / "register.yaml").exists()
