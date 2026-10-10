"""The WelcomeGoodbye plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/info.yaml:1-9
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/Event.kt:18-49
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/config/ConfigSerializer.kt:5-8
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:68-72
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

MESSAGES = (
    "welcome",
    "bye",
    "guild-only",
    "no-permission",
    "invalid-channel",
    "welcome-bind-success",
    "welcome-bind-already",
    "welcome-unbind-success",
    "welcome-unbind-empty",
    "bye-bind-success",
    "bye-bind-already",
    "bye-unbind-success",
    "bye-unbind-empty",
)
LANG_FILES = tuple(
    f"{locale}/{name}"
    for locale in ("en-US", "zh-TW")
    for name in ("register.yaml", *(f"message/{message}.yaml" for message in MESSAGES))
)


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as WelcomeGoodbye."""
    assert discover(["WelcomeGoodbye"]) == [
        PluginInfo(
            "WelcomeGoodbye",
            "xincord.plugins.welcome_goodbye",
            intents=discord.Intents(members=True),
        )
    ]


async def test_the_bot_requests_the_members_intent(bot: Bot) -> None:
    """Requirement: The plugin installs as WelcomeGoodbye."""
    assert bot.loaded == ("WelcomeGoodbye",)
    assert bot.intents.members


async def test_first_load_creates_the_lang_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as WelcomeGoodbye."""
    directory = tmp_path / "plugins" / "WelcomeGoodbye"

    assert bot.loaded == ("WelcomeGoodbye",)
    assert len(LANG_FILES) == 28
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    assert not (directory / "config.yaml").exists()  # v3's only key, enabled, is gone
