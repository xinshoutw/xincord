"""The _Example plugin's entry point and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/Event.kt:17-30
"""

from importlib.resources import files
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

LANG_FILES = (
    "en-US/register.yaml",
    "en-US/message/example.yaml",
    "en-US/message/counter.yaml",
    "zh-TW/register.yaml",
    "zh-TW/message/example.yaml",
    "zh-TW/message/counter.yaml",
)


@pytest.mark.xfail(strict=True, reason="The plugin installs as Example")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as Example."""
    assert discover(["Example"]) == [PluginInfo("Example", "xincord.plugins.example")]


@pytest.mark.xfail(strict=True, reason="The plugin installs as Example")
async def test_first_load_creates_the_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as Example."""
    bot = await load_plugin("Example", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "Example"

    assert bot.loaded == ("Example",)
    bundled = files("xincord.plugins.example").joinpath("config.yaml")
    assert (directory / "config.yaml").read_text(encoding="utf-8") == bundled.read_text(
        encoding="utf-8"
    )
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
