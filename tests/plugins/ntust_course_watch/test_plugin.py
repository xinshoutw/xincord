"""The NtustCourseWatch plugin's entry point and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/resources/info.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/resources/config.yaml:1
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:14-26
"""

from importlib.resources import files
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

BUNDLED = (
    "config.yaml",
    "lang/en-US/register.yaml",
    "lang/en-US/text.yaml",
    "lang/zh-TW/register.yaml",
    "lang/zh-TW/text.yaml",
)


@pytest.mark.xfail(strict=True, reason="The plugin installs as NtustCourseWatch")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as NtustCourseWatch."""
    # No intents beyond discord.py's defaults: v3's info.yaml requested none, and slash commands
    # need none.
    assert discover(["NtustCourseWatch"]) == [
        PluginInfo("NtustCourseWatch", "xincord.plugins.ntust_course_watch")
    ]


@pytest.mark.xfail(strict=True, reason="The plugin installs as NtustCourseWatch")
async def test_first_load_writes_the_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as NtustCourseWatch."""
    bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "NtustCourseWatch"

    assert bot.loaded == ("NtustCourseWatch",)  # the bundled config holds v3's values
    package = files("xincord.plugins.ntust_course_watch")
    for name in BUNDLED:
        written = (directory / name).read_text(encoding="utf-8")
        assert written == package.joinpath(name).read_text(encoding="utf-8"), name
