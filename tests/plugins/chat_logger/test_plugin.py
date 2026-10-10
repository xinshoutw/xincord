"""The ChatLogger plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/info.yaml:1-16
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/build.gradle.kts:1-7
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:23-48
"""

from importlib.resources import files
from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

MESSAGES = (
    "chat-logger@setting",
    "delete",
    "modify-allow",
    "modify-block",
    "on-msg-delete",
    "on-msg-update",
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


@pytest.mark.xfail(strict=True, reason="The plugin installs as ChatLogger")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as ChatLogger."""
    # v3's GUILD_MESSAGES and MESSAGE_CONTENT; v3's SQLiteAPI dependency is the core's store.
    assert discover(["ChatLogger"]) == [
        PluginInfo(
            "ChatLogger",
            "xincord.plugins.chat_logger",
            intents=discord.Intents(guild_messages=True, message_content=True),
        )
    ]


@pytest.mark.xfail(strict=True, reason="The plugin installs as ChatLogger")
async def test_the_bot_requests_the_message_intents(bot: Bot) -> None:
    """Requirement: The plugin installs as ChatLogger."""
    assert bot.loaded == ("ChatLogger",)
    assert bot.intents.guild_messages
    assert bot.intents.message_content  # privileged: the developer portal must allow it


@pytest.mark.xfail(strict=True, reason="The plugin installs as ChatLogger")
async def test_first_load_creates_the_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as ChatLogger."""
    directory = tmp_path / "plugins" / "ChatLogger"
    bundled = files("xincord.plugins.chat_logger").joinpath("config.yaml")

    assert bot.loaded == ("ChatLogger",)
    assert len(LANG_FILES) == 16
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    config = (directory / "config.yaml").read_text(encoding="utf-8")
    assert config == bundled.read_text(encoding="utf-8")
