"""The Ticket plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/info.yaml:1-9
    XsDiscordBotKt@3a59607:Plugins/Ticket/build.gradle.kts:1-3
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Event.kt:18-34
"""

from typing import TYPE_CHECKING

from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot

MESSAGES = (
    "add-ticket",
    "confirm-add",
    "confirm-create",
    "create-ticket",
    "modify-admin-role",
    "modify-btn-color",
    "modify-category",
)
MODALS = (
    "modify-author",
    "modify-btn-text",
    "modify-content",
    "modify-embed-color",
    "modify-reason-title",
    "press-ticket",
    "preview-reason",
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
    """Requirement: The plugin installs as Ticket."""
    # No intents: guild leaves need only discord.py's default guilds intent, the members come with
    # the interactions, and the archive reads the history through REST.
    assert discover(["Ticket"]) == [PluginInfo("Ticket", "xincord.plugins.ticket")]


async def test_first_load_creates_the_files(bot: Bot, tmp_path: Path) -> None:
    """Requirement: The plugin installs as Ticket."""
    directory = tmp_path / "plugins" / "Ticket"

    assert bot.loaded == ("Ticket",)
    assert len(LANG_FILES) == 32
    for name in LANG_FILES:
        assert (directory / "lang" / name).is_file()
    # v3's only key was enabled, which the core's plugins list replaces.
    assert not (directory / "config.yaml").exists()
