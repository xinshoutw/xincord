"""Problems with notices are reported: a missing owner, Discord's refusals, unpostable templates.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:28-37
"""

import logging
from typing import TYPE_CHECKING

import pytest

from discord_fakes import forbidden, not_found, server_error
from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import Scene
    from xincord.core.storage import Store

LOOKUP = "GET /guilds/10/members/20"  # Discord's member request for the owner
POST = "POST /channels/31/messages"  # the notice in ticket-alice
CONFIG = "guild_id: 10\nuser_id: 20\nprefix: [ticket-]\ndelay_millis: 2000\n"


def plugin_logs(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    """The plugin's log lines at warning level and above."""
    return [
        (record.levelno, record.getMessage())
        for record in caplog.records
        if record.name.startswith("xincord.plugins.ticket_away_notice")
        and record.levelno >= logging.WARNING
    ]


@pytest.mark.xfail(strict=True, reason="Problems with notices are reported")
async def test_owner_not_a_member(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems with notices are reported."""
    await scene.uncache_owner()
    scene.rest.errors[LOOKUP] = not_found("Unknown Member")

    with caplog.at_level(logging.WARNING):
        await scene.create(31, "ticket-alice")
        await scene.settle()

    assert scene.notices() == []
    assert scene.clock.delays == []
    assert plugin_logs(caplog) == [
        (logging.WARNING, "TicketAwayNotice posts no notice in guild (10): user 20 is not a member")
    ]


@pytest.mark.xfail(strict=True, reason="Problems with notices are reported")
async def test_refused_lookup(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems with notices are reported."""
    await scene.uncache_owner()
    error = server_error()  # after discord.py's own retries
    scene.rest.errors[LOOKUP] = error

    with caplog.at_level(logging.WARNING):
        await scene.create(31, "ticket-alice")
        await scene.settle()

    assert scene.notices() == []
    assert plugin_logs(caplog) == [
        (logging.WARNING, f"TicketAwayNotice cannot look up user 20 in guild (10): {error}")
    ]


@pytest.mark.xfail(strict=True, reason="Problems with notices are reported")
async def test_refused_notice(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems with notices are reported."""
    error = forbidden()  # the bot lacks Send Messages there
    scene.rest.errors[POST] = error

    with caplog.at_level(logging.WARNING):
        await scene.create(31, "ticket-alice")
        await scene.settle()

    assert plugin_logs(caplog) == [
        (
            logging.WARNING,
            f"TicketAwayNotice cannot post the notice in ticket-alice (31) of guild (10): {error}",
        )
    ]


@pytest.mark.xfail(strict=True, reason="Problems with notices are reported")
async def test_unexpected_failure(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems with notices are reported."""
    scene.rest.errors[POST] = ConnectionResetError("Connection reset by peer")

    with caplog.at_level(logging.WARNING):
        await scene.create(31, "ticket-alice")
        await scene.settle()

    assert plugin_logs(caplog) == [
        (logging.ERROR, "TicketAwayNotice failed to post a notice in ticket-alice (31)")
    ]
    [record] = [found for found in caplog.records if found.levelno == logging.ERROR]
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], ConnectionResetError)


@pytest.mark.xfail(strict=True, reason="Problems with notices are reported")
@pytest.mark.parametrize(
    ("template", "reason"),
    [
        (
            (
                'embeds: [{description: "away"}]\n'
                "components:\n  - !ButtonsComponent\n"
                "    buttons: [{uid: {action: ok}, label: OK}]\n"
            ),
            "components with a uid need an ID builder",
        ),
        ("model_key: notice\n", "no model named 'notice' was supplied"),
    ],
    ids=["uid", "model_key"],
)
async def test_template_that_cannot_be_posted(
    template: str, reason: str, store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Problems with notices are reported."""
    root = tmp_path / "plugins"
    path = root / "TicketAwayNotice" / "lang" / "zh-TW" / "message" / "not-online.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(template, encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        bot = await load_plugin("TicketAwayNotice", root, store, config=CONFIG)

    assert bot.loaded == ()
    assert f"zh-TW/message/not-online.yaml: cannot be posted: {reason}" in caplog.text
