"""The NtustAnnouncements plugin's entry point and bundled config.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-19
"""

from importlib.resources import files
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store


@pytest.mark.xfail(strict=True, reason="The plugin installs as NtustAnnouncements")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as NtustAnnouncements."""
    # No intents beyond discord.py's defaults: v3's info.yaml requested none.
    assert discover(["NtustAnnouncements"]) == [
        PluginInfo("NtustAnnouncements", "xincord.plugins.ntust_announcements")
    ]


@pytest.mark.xfail(strict=True, reason="The plugin installs as NtustAnnouncements")
async def test_first_load_writes_the_config(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as NtustAnnouncements."""
    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "NtustAnnouncements"

    assert bot.loaded == ()  # the bundled keys and channels wait for the operator
    bundled = files("xincord.plugins.ntust_announcements").joinpath("config.yaml")
    written = (directory / "config.yaml").read_text(encoding="utf-8")
    assert written == bundled.read_text(encoding="utf-8")
    assert not (directory / "lang").exists()  # v3 had no lang files
