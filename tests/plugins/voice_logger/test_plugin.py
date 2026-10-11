"""The VoiceLogger plugin's entry point, intents and bundled files."""

from typing import TYPE_CHECKING

import discord

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

MESSAGES = (
    "voice-logger@setting",
    "delete",
    "modify-allow",
    "modify-block",
    "on-channel-join",
    "on-channel-left",
    "on-channel-switch",
    "on-status-new",
    "on-status-update",
    "on-status-delete",
)
LANG_FILES = tuple(
    f"{locale}/{name}"
    for locale in ("en-US", "zh-TW")
    for name in (
        "register.yaml",
        "placeholder.yaml",
        *(f"message/{message}.yaml" for message in MESSAGES),
    )
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as VoiceLogger."""
    # The voice states intent is v3's GUILD_VOICE_STATES; discord.py's defaults hold it too, and
    # the guilds intent, which carries the voice channel status updates.
    assert discover(["VoiceLogger"]) == [
        PluginInfo(
            "VoiceLogger",
            "xincord.plugins.voice_logger",
            intents=discord.Intents(voice_states=True),
        )
    ]


async def test_the_bot_requests_the_voice_states_intent(bot: Bot) -> None:
    """Requirement: The plugin installs as VoiceLogger."""
    assert bot.loaded == ("VoiceLogger",)
    assert bot.intents.voice_states
    assert bot.intents.guilds


async def test_first_load_creates_the_lang_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as VoiceLogger."""
    directory = tmp_path / "plugins" / "VoiceLogger"

    assert bot.loaded == ("VoiceLogger",)
    assert len(LANG_FILES) == 24
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    assert not (directory / "config.yaml").exists()  # v3's only key, enabled, is gone
