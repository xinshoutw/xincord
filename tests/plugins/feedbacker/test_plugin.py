"""The Feedbacker plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/info.yaml:1-10
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Event.kt:15-31
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/config.yaml:1-5
"""

from importlib.resources import files
from typing import TYPE_CHECKING

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

TEMPLATES = ("message/ask-message.yaml", "message/print-result.yaml", "modal/fill-form.yaml")
LANG_FILES = tuple(
    f"{locale}/{name}" for locale in ("en-US", "zh-TW") for name in ("register.yaml", *TEMPLATES)
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as Feedbacker."""
    # No dependencies and no intents: Discord resolves the member option and the submitter, and
    # the submit channel comes from the guild cache of discord.py's default intents.
    assert discover(["Feedbacker"]) == [PluginInfo("Feedbacker", "xincord.plugins.feedbacker")]


async def test_first_load_creates_the_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as Feedbacker."""
    bot = await load_plugin("Feedbacker", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "Feedbacker"

    assert bot.loaded == ("Feedbacker",)
    written = (directory / "config.yaml").read_text(encoding="utf-8")
    bundled = files("xincord.plugins.feedbacker").joinpath("config.yaml")
    assert written == bundled.read_text(encoding="utf-8")
    assert len(LANG_FILES) == 8
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
