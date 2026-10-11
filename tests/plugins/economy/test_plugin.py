"""The Economy plugin's entry point, intents and bundled files."""

from importlib.resources import files
from typing import TYPE_CHECKING

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

MESSAGES = (
    "balance",
    "no-permission",
    "top-money",
    "top-cost",
    "add-money",
    "remove-money",
    "set-money",
    "add-cost",
    "remove-cost",
    "set-cost",
)
LANG_FILES = tuple(
    f"{locale}/{name}"
    for locale in ("en-US", "zh-TW")
    for name in ("register.yaml", *(f"message/{message}.yaml" for message in MESSAGES))
)
ADMINS = "admin_id: [1]\n"  # an operator's config.yaml that lists the administrator 1


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as Economy."""
    # No dependencies: v3's GoogleSheetAPI served only the dead Sheets storage. No intents: Discord
    # resolves the member option, and nothing reads the member cache.
    assert discover(["Economy"]) == [PluginInfo("Economy", "xincord.plugins.economy")]


async def test_first_load_creates_the_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as Economy."""
    await load_plugin("Economy", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "Economy"

    written = (directory / "config.yaml").read_text(encoding="utf-8")
    bundled = files("xincord.plugins.economy").joinpath("config.yaml")
    assert written == bundled.read_text(encoding="utf-8")
    assert len(LANG_FILES) == 22
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()

    bot = await load_plugin("Economy", tmp_path / "plugins", store, config=ADMINS)

    assert bot.loaded == ("Economy",)
