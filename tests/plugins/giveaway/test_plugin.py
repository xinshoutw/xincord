"""The Giveaway plugin's entry point, intents and bundled files."""

from importlib.resources import files
from typing import TYPE_CHECKING

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

MESSAGES = (
    "auto-draw-result",
    "create-cancelled",
    "create-failed",
    "create-finished",
    "create-giveaway",
    "draw-result",
    "giveaway-post",
)
MODALS = (
    "add-prize",
    "set-description",
    "set-end-time",
    "set-sponsor",
    "set-thumbnail",
    "set-title",
)
LANG_FILES = tuple(
    f"{locale}/{name}"
    for locale in ("en-US", "zh-TW")
    for name in (
        "register.yaml",
        "text.yaml",
        *(f"message/{message}.yaml" for message in MESSAGES),
        *(f"modal/{modal}.yaml" for modal in MODALS),
    )
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as Giveaway."""
    # No intents: guild leaves need only discord.py's default guilds intent, and the members come
    # with the interactions.
    assert discover(["Giveaway"]) == [PluginInfo("Giveaway", "xincord.plugins.giveaway")]


async def test_first_load_creates_the_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as Giveaway."""
    directory = tmp_path / "plugins" / "Giveaway"
    bundled = files("xincord.plugins.giveaway").joinpath("config.yaml")

    assert bot.loaded == ("Giveaway",)
    assert len(LANG_FILES) == 30
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    config = (directory / "config.yaml").read_text(encoding="utf-8")
    assert config == bundled.read_text(encoding="utf-8")
