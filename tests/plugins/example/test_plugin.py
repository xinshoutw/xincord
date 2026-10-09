"""The _Example plugin's entry point and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/Event.kt:17-30
"""

from importlib.resources import files
from typing import TYPE_CHECKING

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

LANG_FILES = (
    "en-US/register.yaml",
    "en-US/message/example.yaml",
    "en-US/message/counter.yaml",
    "zh-TW/register.yaml",
    "zh-TW/message/example.yaml",
    "zh-TW/message/counter.yaml",
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as _Example."""
    assert discover(["_Example"]) == [PluginInfo("_Example", "xincord.plugins.example")]


async def test_first_load_creates_the_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as _Example."""
    directory = tmp_path / "plugins" / "_Example"

    assert bot.loaded == ("_Example",)
    bundled = files("xincord.plugins.example").joinpath("config.yaml")
    assert (directory / "config.yaml").read_text(encoding="utf-8") == bundled.read_text(
        encoding="utf-8"
    )
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
