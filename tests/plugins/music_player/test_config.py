"""The MusicPlayer config: the Lavalink node, and v3's keys that had an effect."""

import logging
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import FIXTURES, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.music_player.cog import MusicPlayer
    from xincord.plugins.music_player.config import Config

NODE = 'lavalink:\n  password: "example-password"\n'
# v3's bundled config.yaml as written (no final newline), with the node that xincord needs.
V3_CONFIG = (FIXTURES / "plugins" / "music_player" / "v3_config.yaml").read_text(encoding="utf-8")
# The keys of v3's file that v3 never read, or that moved to the node (engines), each warned about.
UNUSED = (
    "enabled",
    "command_message_acknowledges",
    "engines",
    "player.max_queue_size",
    "player.search_timeout",
    "player.playback",
    "player.cache",
    "messages.announce_new_track",
    "messages.use_enhanced_embeds",
    "messages.embeds",
    "features",
    "performance",
    "cache",
    "developer",
)
V3_EMOJIS = {
    "progress_white_start": "music_player__line_white_start",
    "progress_white_full": "music_player__line_white_full",
    "progress_white_end": "music_player__line_white_end",
    "progress_black": "music_player__line_black",
    "progress_black_end": "music_player__line_black_end",
    "media_play": "music_player__media_play",
    "media_pause": "music_player__media_pause",
    "media_ordered": "music_player__media_ordered",
    "media_repeat_once": "music_player__media_repeat_once",
    # v3's templates named these by the author's application IDs.
    "media_previous": "music_player__media_previous",
    "media_pause_resume": "music_player__media_pause_resume",
    "media_next": "music_player__media_next",
    "media_disconnect": "music_player__media_disconnect",
}


def config_of(bot: Bot) -> Config:
    """The loaded plugin's config."""
    return cast("MusicPlayer", bot.get_cog("MusicPlayer")).config


async def test_v3_config_file_with_a_node(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the node, the player's defaults, the errors and the emojis."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin(
            "MusicPlayer", tmp_path / "plugins", store, config=f"{V3_CONFIG}\n{NODE}"
        )

    assert bot.loaded == ("MusicPlayer",)
    config = config_of(bot)
    assert (config.lavalink.host, config.lavalink.port) == ("lavalink", 2333)
    assert config.lavalink.password == "example-password"
    assert config.player.default_volume == 40  # v3's
    assert config.player.auto_leave_timeout == 600000  # v3's, which now takes effect
    assert config.messages.show_detailed_errors is True
    assert config.emojis.model_dump() == V3_EMOJIS
    for key in UNUSED:
        assert f"unknown key {key}\n" in caplog.text


async def test_bundled_config_waits_for_the_password(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the node, the player's defaults, the errors and the emojis."""
    with caplog.at_level(logging.ERROR):
        bot = await load_plugin("MusicPlayer", tmp_path / "plugins", store)

    assert bot.loaded == ()
    assert "lavalink.password" in caplog.text
    assert "unknown key" not in caplog.text


async def test_bundled_config_with_a_password(tmp_path: Path, store: Store) -> None:
    """Requirement: The config names the node, the player's defaults, the errors and the emojis."""
    root = tmp_path / "plugins"
    await load_plugin("MusicPlayer", root, store)  # writes the bundled file
    path = root / "MusicPlayer" / "config.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace('password: ""', 'password: "example-password"'),
        encoding="utf-8",
    )

    bot = await load_plugin("MusicPlayer", root, store)

    assert bot.loaded == ("MusicPlayer",)
    config = config_of(bot)
    assert (config.player.default_volume, config.player.auto_leave_timeout) == (40, 600000)
    assert config.emojis.model_dump() == V3_EMOJIS


@pytest.mark.parametrize(
    ("text", "key"),
    [
        pytest.param(
            f"{NODE}player:\n  default_volume: 101\n", "player.default_volume", id="volume"
        ),
        pytest.param(
            f"{NODE}player:\n  auto_leave_timeout: -1\n", "player.auto_leave_timeout", id="timeout"
        ),
        pytest.param('lavalink:\n  port: 0\n  password: "p"\n', "lavalink.port", id="port"),
        pytest.param('lavalink:\n  host: ""\n  password: "p"\n', "lavalink.host", id="host"),
        pytest.param('lavalink:\n  password: "  "\n', "lavalink.password", id="blank password"),
        pytest.param(
            f'{NODE}emojis:\n  media_play: "media play"\n', "emojis.media_play", id="emoji name"
        ),
        pytest.param("player: {}\n", "lavalink", id="no node"),
    ],
)
async def test_invalid_values(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture, text: str, key: str
) -> None:
    """Requirement: The config names the node, the player's defaults, the errors and the emojis."""
    with caplog.at_level(logging.ERROR):
        bot = await load_plugin("MusicPlayer", tmp_path / "plugins", store, config=text)

    assert bot.loaded == ()
    assert f"config.yaml: {key}:" in caplog.text


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("lavalink:\n  password: 31415926535\n", id="a number"),
        pytest.param("lavalink: 31415926535\n", id="no mapping"),
        pytest.param("lavalink:\n  password: [31415926535]\n", id="a list"),
    ],
)
async def test_the_password_stays_hidden(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture, text: str
) -> None:
    """Requirement: The config names the node, the player's defaults, the errors and the emojis."""
    with caplog.at_level(logging.DEBUG):
        bot = await load_plugin("MusicPlayer", tmp_path / "plugins", store, config=text)

    assert bot.loaded == ()
    assert "lavalink" in caplog.text
    assert "31415926535" not in caplog.text
