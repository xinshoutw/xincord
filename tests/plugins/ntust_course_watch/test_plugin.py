"""The NtustCourseWatch plugin's entry point and bundled files."""

from importlib.resources import files
from typing import TYPE_CHECKING

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


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as NtustCourseWatch."""
    # No intents beyond discord.py's defaults: slash commands need none.
    assert discover(["NtustCourseWatch"]) == [
        PluginInfo("NtustCourseWatch", "xincord.plugins.ntust_course_watch")
    ]


async def test_first_load_writes_the_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as NtustCourseWatch."""
    bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "NtustCourseWatch"

    assert bot.loaded == ("NtustCourseWatch",)  # the bundled config holds the defaults
    package = files("xincord.plugins.ntust_course_watch")
    for name in BUNDLED:
        written = (directory / name).read_text(encoding="utf-8")
        assert written == package.joinpath(name).read_text(encoding="utf-8"), name
