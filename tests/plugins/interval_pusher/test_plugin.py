"""The IntervalPusher plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/Event.kt:10-31
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/resources/config.yaml:1-4
"""

from importlib.resources import files
from typing import TYPE_CHECKING

import pytest
import yaml

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

XFAIL = pytest.mark.xfail(strict=True, reason="The plugin installs as IntervalPusher")


@XFAIL
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as IntervalPusher."""
    # No dependencies and no intents: v3 handled no gateway event.
    assert discover(["IntervalPusher"]) == [
        PluginInfo("IntervalPusher", "xincord.plugins.interval_pusher")
    ]


@XFAIL
async def test_first_load_creates_the_config(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as IntervalPusher."""
    bot = await load_plugin("IntervalPusher", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "IntervalPusher"

    assert bot.loaded == ("IntervalPusher",)
    written = (directory / "config.yaml").read_text(encoding="utf-8")
    bundled = files("xincord.plugins.interval_pusher").joinpath("config.yaml")
    assert written == bundled.read_text(encoding="utf-8")
    assert yaml.safe_load(written) == {"listeners": []}
    assert not (directory / "lang").exists()  # v3 had no text
