"""The TicketAwayNotice plugin's entry point, intents and bundled files.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/resources/info.yaml:1-13
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:7-14
"""

from importlib.resources import files
from typing import TYPE_CHECKING

import discord

from plugin_fakes import load_plugin
from xincord.core.plugins import PluginInfo, discover

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store

NOTICE = "lang/zh-TW/message/not-online.yaml"


def test_discovered_by_name() -> None:
    """Requirement: The plugin installs as TicketAwayNotice."""
    assert discover(["TicketAwayNotice"]) == [
        PluginInfo(
            "TicketAwayNotice",
            "xincord.plugins.ticket_away_notice",
            intents=discord.Intents(members=True, presences=True),
        )
    ]


async def test_the_bot_requests_the_intents(bot: Bot) -> None:
    """Requirement: The plugin installs as TicketAwayNotice."""
    assert bot.loaded == ("TicketAwayNotice",)
    assert bot.intents.members
    assert bot.intents.presences


async def test_first_load_writes_the_files(store: Store, tmp_path: Path) -> None:
    """Requirement: The plugin installs as TicketAwayNotice."""
    bot = await load_plugin("TicketAwayNotice", tmp_path / "plugins", store)
    directory = tmp_path / "plugins" / "TicketAwayNotice"

    assert bot.loaded == ()  # the bundled IDs wait for the operator
    bundled = files("xincord.plugins.ticket_away_notice")
    for name in ("config.yaml", NOTICE):
        written = (directory / name).read_text(encoding="utf-8")
        assert written == bundled.joinpath(name).read_text(encoding="utf-8")
    lang = directory / "lang"
    assert [path.relative_to(lang).as_posix() for path in lang.rglob("*.yaml")] == [
        "zh-TW/message/not-online.yaml"  # v3 had no commands, so no register.yaml
    ]
