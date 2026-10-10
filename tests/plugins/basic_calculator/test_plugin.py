"""The BasicCalculator plugin's entry point and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/Event.kt:17-30
"""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

LANG_FILES = (
    "en-US/register.yaml",
    "en-US/message/basic-calculate.yaml",
    "en-US/message/error.yaml",
    "zh-TW/register.yaml",
    "zh-TW/message/basic-calculate.yaml",
    "zh-TW/message/error.yaml",
)


@pytest.mark.xfail(strict=True, reason="The plugin installs as Calculator")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as Calculator."""
    assert discover(["Calculator"]) == [PluginInfo("Calculator", "xincord.plugins.calculator")]


@pytest.mark.xfail(strict=True, reason="The plugin installs as Calculator")
async def test_first_load_creates_the_lang_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as Calculator."""
    bot = await load_plugin("Calculator", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "Calculator"

    assert bot.loaded == ("Calculator",)
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    assert not (directory / "config.yaml").exists()  # v3's only key, enabled, is gone
