"""The WelcomeByeGuild plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/info.yaml:1-9
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/Event.kt:18-49
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/config/ConfigSerializer.kt:5-8
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:68-72
"""

from typing import TYPE_CHECKING

import discord
import pytest

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

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


@pytest.mark.xfail(strict=True, reason="The plugin installs as WelcomeGoodbye")
def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as WelcomeGoodbye."""
    assert discover(["WelcomeGoodbye"]) == [
        PluginInfo(
            "WelcomeGoodbye",
            "xincord.plugins.welcome_goodbye",
            intents=discord.Intents(members=True),
        )
    ]


@pytest.mark.xfail(strict=True, reason="The plugin installs as WelcomeGoodbye")
async def test_the_bot_requests_the_members_intent(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as WelcomeGoodbye."""
    bot = await load_plugin("WelcomeGoodbye", tmp_path / "plugins", store)

    assert bot.loaded == ("WelcomeGoodbye",)
    assert bot.intents.members


@pytest.mark.xfail(strict=True, reason="The plugin installs as WelcomeGoodbye")
async def test_first_load_creates_the_lang_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as WelcomeGoodbye."""
    bot = await load_plugin("WelcomeGoodbye", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "WelcomeGoodbye"

    assert bot.loaded == ("WelcomeGoodbye",)
    assert len(LANG_FILES) == 28
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    assert not (directory / "config.yaml").exists()  # v3's only key, enabled, is gone
