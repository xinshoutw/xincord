"""The SimpleCommand plugin's entry point and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:14-30
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/config/ConfigSerializer.kt:5-8
"""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

LANG_FILES = (
    "zh-TW/register.yaml",
    "zh-TW/message/cub-none-card.yaml",
    "zh-TW/message/tsib-none-card.yaml",
    "zh-TW/message/ctcb-none-card.yaml",
    "zh-TW/message/ctcb-remit.yaml",
    "zh-TW/message/chpytwtp-remit.yaml",
)


@pytest.mark.xfail(strict=True, reason="The plugin installs as CustomCommands")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as CustomCommands."""
    assert discover(["CustomCommands"]) == [
        PluginInfo("CustomCommands", "xincord.plugins.custom_commands")
    ]


@pytest.mark.xfail(strict=True, reason="The plugin installs as CustomCommands")
async def test_first_load_creates_the_lang_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as CustomCommands."""
    bot = await load_plugin("CustomCommands", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "CustomCommands"

    assert bot.loaded == ("CustomCommands",)
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    assert not (directory / "config.yaml").exists()  # v3's only key, enabled, is gone
