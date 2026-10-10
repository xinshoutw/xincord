"""The SimpleCommand plugin's entry point and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:14-30
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/config/ConfigSerializer.kt:5-8
"""

from typing import TYPE_CHECKING

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

LANG_FILES = (
    "zh-TW/register.yaml",
    "zh-TW/message/cub-none-card.yaml",
    "zh-TW/message/tsib-none-card.yaml",
    "zh-TW/message/ctcb-none-card.yaml",
    "zh-TW/message/ctcb-remit.yaml",
    "zh-TW/message/chpytwtp-remit.yaml",
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as SimpleCommand."""
    assert discover(["SimpleCommand"]) == [
        PluginInfo("SimpleCommand", "xincord.plugins.simple_command")
    ]


async def test_first_load_creates_the_lang_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as SimpleCommand."""
    directory = tmp_path / "plugins" / "SimpleCommand"

    assert bot.loaded == ("SimpleCommand",)
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    assert not (directory / "config.yaml").exists()  # v3's only key, enabled, is gone
