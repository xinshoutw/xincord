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


@pytest.mark.xfail(strict=True, reason="The plugin installs as UptimeHeartbeat")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as UptimeHeartbeat."""
    # No dependencies and no intents: v3 handled no gateway event.
    assert discover(["UptimeHeartbeat"]) == [
        PluginInfo("UptimeHeartbeat", "xincord.plugins.uptime_heartbeat")
    ]


@pytest.mark.xfail(strict=True, reason="The plugin installs as UptimeHeartbeat")
async def test_first_load_creates_the_config(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as UptimeHeartbeat."""
    bot = await load_plugin("UptimeHeartbeat", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "UptimeHeartbeat"

    assert bot.loaded == ("UptimeHeartbeat",)
    written = (directory / "config.yaml").read_text(encoding="utf-8")
    bundled = files("xincord.plugins.uptime_heartbeat").joinpath("config.yaml")
    assert written == bundled.read_text(encoding="utf-8")
    assert yaml.safe_load(written) == {"listeners": []}
    assert not (directory / "lang").exists()  # v3 had no text
