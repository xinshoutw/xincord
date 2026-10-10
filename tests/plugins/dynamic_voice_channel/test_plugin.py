"""The DynamicVoiceChannel plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/resources/info.yaml:1-21
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/build.gradle.kts:1-3
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/Event.kt:21-37
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/config/ConfigSerializer.kt:5-8
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

MESSAGES = ("bind-success", "must-under-category", "unbind-fail", "unbind-success")
LANG_FILES = tuple(
    f"{locale}/{name}"
    for locale in ("en-US", "zh-TW")
    for name in ("register.yaml", *(f"message/{message}.yaml" for message in MESSAGES))
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as DynamicVoiceChannel."""
    # No dependencies: v3's SQLiteAPI was never used. The voice states intent is v3's
    # GUILD_VOICE_STATES; discord.py's defaults hold it too.
    assert discover(["DynamicVoiceChannel"]) == [
        PluginInfo(
            "DynamicVoiceChannel",
            "xincord.plugins.dynamic_voice_channel",
            intents=discord.Intents(voice_states=True),
        )
    ]


async def test_the_bot_requests_the_voice_states_intent(bot: Bot) -> None:
    """Requirement: The plugin installs as DynamicVoiceChannel."""
    assert bot.loaded == ("DynamicVoiceChannel",)
    assert bot.intents.voice_states


async def test_first_load_creates_the_lang_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as DynamicVoiceChannel."""
    directory = tmp_path / "plugins" / "DynamicVoiceChannel"

    assert bot.loaded == ("DynamicVoiceChannel",)
    assert len(LANG_FILES) == 10
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    assert not (directory / "config.yaml").exists()  # v3's only key, enabled, is gone
