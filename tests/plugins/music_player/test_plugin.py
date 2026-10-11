"""The MusicPlayer plugin's entry point and bundled files."""

from importlib.resources import files
from typing import TYPE_CHECKING

import discord

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

TEMPLATES = ("now-playing", "pause", "play", "queue", "resume", "skip", "volume")
BUNDLED = (
    "config.yaml",
    *(
        f"lang/{locale}/{name}"
        for locale in ("en-US", "zh-TW")
        for name in (
            "register.yaml",
            "text.yaml",
            *(f"message/{template}.yaml" for template in TEMPLATES),
        )
    ),
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as MusicPlayer."""
    # v3's info.yaml: GUILD_VOICE_STATES; AudioAPI, its only dependency, folds into the plugin.
    assert discover(["MusicPlayer"]) == [
        PluginInfo(
            "MusicPlayer",
            "xincord.plugins.music_player",
            intents=discord.Intents(voice_states=True),
        )
    ]


async def test_first_load_writes_the_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as MusicPlayer."""
    bot = await load_plugin("MusicPlayer", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "MusicPlayer"

    assert bot.loaded == ()  # the bundled config waits for the node's password
    package = files("xincord.plugins.music_player")
    for name in BUNDLED:
        written = (directory / name).read_text(encoding="utf-8")
        assert written == package.joinpath(name).read_text(encoding="utf-8"), name
