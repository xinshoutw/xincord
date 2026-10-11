"""Problems with notices are reported: a missing owner, Discord's refusals, unpostable templates."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import forbidden, not_found, server_error
from plugin_fakes import load_plugin, unclosed

if TYPE_CHECKING:
    from conftest import Scene
    from xincord.core.storage import Store

LOOKUP = "GET /guilds/10/members/20"  # Discord's member request for the owner
POST = "POST /channels/31/messages"  # the notice in ticket-alice
CONFIG = "guild_id: 10\nuser_id: 20\nprefix: [ticket-]\ndelay_millis: 2000\n"
# Discord takes at most ten embeds in a message; discord.py refuses more before sending.
ELEVEN_EMBEDS = "embeds:\n" + "".join(f"  - {{description: n{index}}}\n" for index in range(11))
# An operator's notice in Components V2 that attaches a file of the fixtures.
HOURS = Path(__file__).parents[2] / "fixtures" / "plugins" / "ticket_away_notice" / "hours.txt"
WITH_FILE = (
    "is_components_v2: true\n"
    "components_v2:\n"
    "  - {type: text_display, content: The owner is away.}\n"
    f"  - {{type: file_display, file_path: '{HOURS}'}}\n"
)


def plugin_logs(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    """The plugin's log lines at warning level and above."""
    return [
        (record.levelno, record.getMessage())
        for record in caplog.records
        if record.name.startswith("xincord.plugins.ticket_away_notice")
        and record.levelno >= logging.WARNING
    ]


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
    log = await refused(template, store, tmp_path, caplog)

    assert f"zh-TW/message/not-online.yaml: cannot be posted: {reason}" in log


@pytest.mark.parametrize(
    ("template", "reason"),
    [
        (ELEVEN_EMBEDS, "11 embeds, more than the 10 that Discord takes"),
        ('content: ""\n', "it renders an empty message"),
    ],
    ids=["eleven-embeds", "empty"],
)
async def test_template_that_discord_refuses(
    template: str, reason: str, store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Problems with notices are reported."""
    log = await refused(template, store, tmp_path, caplog)

    assert f"zh-TW/message/not-online.yaml: cannot be posted: {reason}" in log


async def refused(
    template: str, store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> str:
    """Load the plugin with the operator's notice ``template``; check that it did not load and
    return the log."""
    root = tmp_path / "plugins"
    path = root / "TicketAwayNotice" / "lang" / "zh-TW" / "message" / "not-online.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(template, encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        bot = await load_plugin("TicketAwayNotice", root, store, config=CONFIG)

    assert bot.loaded == ()
    return caplog.text


@pytest.mark.parametrize("notice", [WITH_FILE], ids=["file"])
async def test_template_with_a_file(scene: Scene) -> None:
    """Requirement: Problems with notices are reported."""
    await scene.create(31, "ticket-alice")
    await scene.settle()

    [request] = [request for key, request in scene.rest.sent if key == POST]
    parts = cast("list[dict[str, Any]]", request["form"])
    assert [part.get("filename") for part in parts[1:]] == ["hours.txt"]
    assert unclosed() == []  # the load's check and the notice closed their files
