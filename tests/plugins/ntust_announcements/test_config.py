"""The NtustAnnouncements config: bulletin's API, the intervals and the boards."""

from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import yaml

from plugin_fakes import load_plugin
from xincord.core.config import ConfigError, parse_model
from xincord.plugins.ntust_announcements.config import Config

if TYPE_CHECKING:
    from xincord.core.storage import Store
    from xincord.plugins.ntust_announcements.cog import NtustAnnouncements

MAIN_OFFICE = "".join(map(chr, (0x3010, 0x8655, 0x672C, 0x90E8, 0x3011)))  # the office's prefix
BOARDS = """\
boards:
  - name: STUDENT_DORMITORY
    board: "1053-1436"
    channel-id: 101
  - name: STUDENT_AFFAIRS
    board: "1053"
    channel-id: 0
    title-prefix: "[Office]"
"""
OPERATOR = f"""\
enabled: true
api-url: "http://bulletin-internal:8000/api/v1/"
poll-interval: 30
rendition-wait: 0
{BOARDS}"""
# The scraper's file: its keys only warn, and its boards lack `board`.
OLDER = """\
fetch-interval: 3600
api-keys: ["first-key"]
prompt: "{{page_url}} {{base_url}} {{now}} {{html}}"
boards:
  - name: STUDENT_DORMITORY
    url: "https://student.ntust.edu.tw/p/403-1053-1436-1.php"
    layout: student-affairs
    channel-id: 101
  - name: LANGUAGE_CENTER_RECRUITMENT
    url: "https://lc.ntust.edu.tw/p/403-1070-1626-1.php"
    layout: language-center
    channel-id: 102
"""
# The boards that the scraper read, in its order, with their keys.
SCRAPED = [
    ("STUDENT_DORMITORY", "1053-1436"),
    ("STUDENT_AID", "1053-1437"),
    ("STUDENT_GUIDANCE", "1053-1439"),
    ("STUDENT_ACTIVITY", "1053-1440"),
    ("STUDENT_RESOURCE_ROOM", "1053-1443"),
    ("STUDENT_MAIN_OFFICE", "1053-1435"),
    ("ACADEMIC_MAIN_OFFICE", "1048-1413"),
    ("ACADEMIC_GRADUATE_EDUCATION", "1048-1414"),
    ("ACADEMIC_REGISTRATION", "1048-1415"),
    ("ACADEMIC_COURSE", "1048-1416"),
    ("ACADEMIC_COMPREHENSIVE_BUSINESS", "1048-1417"),
    ("LANGUAGE_CENTER_RECRUITMENT", "1070-1626"),
    ("LANGUAGE_CENTER_EXEMPTION_REWARD", "1070-1627"),
    ("LANGUAGE_CENTER_HONOR_LIST", "1070-1051"),
    ("LANGUAGE_CENTER_FRESHMAN", "1070-1628"),
    ("LANGUAGE_CENTER_ENGLISH_WORDS", "1070-1828"),
    ("LANGUAGE_CENTER_EXTERNAL", "1070-1829"),
    ("LANGUAGE_CENTER_ACTIVITY", "1070-1050"),
]


def parse(text: str) -> Config:
    """``text`` read as the plugin's config.yaml."""
    return parse_model(Path("config.yaml"), yaml.safe_load(text), Config)


def bundled() -> dict[str, Any]:
    """The bundled config.yaml."""
    text = files("xincord.plugins.ntust_announcements").joinpath("config.yaml").read_text("utf-8")
    return yaml.safe_load(text)


async def test_an_operators_config_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the feed and the boards."""
    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=OPERATOR)

    assert bot.loaded == ("NtustAnnouncements",)
    config = cast("NtustAnnouncements", bot.get_cog("NtustAnnouncements")).config
    assert (config.api_url, config.poll_interval, config.rendition_wait) == (
        "http://bulletin-internal:8000/api/v1",
        30,
        0,
    )
    assert [(b.name, b.board, b.channel_id, b.title_prefix) for b in config.boards] == [
        ("STUDENT_DORMITORY", "1053-1436", 101, ""),
        ("STUDENT_AFFAIRS", "1053", 0, "[Office]"),
    ]
    assert "enabled" in caplog.text


def test_defaults() -> None:
    """Requirement: The config names the feed and the boards."""
    config = parse(BOARDS)

    assert (config.api_url, config.poll_interval, config.rendition_wait) == (
        "https://bulletin.ntust.org/api/v1",
        60,
        3600,
    )


async def test_an_older_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the feed and the boards."""
    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=OLDER)

    assert bot.loaded == ()
    assert "boards.0.board: Field required" in caplog.text
    assert "boards.1.board: Field required" in caplog.text


async def test_bundled_config(tmp_path: Path, store: Store) -> None:
    """Requirement: The config names the feed and the boards."""
    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store)

    assert bot.loaded == ("NtustAnnouncements",)
    cog = cast("NtustAnnouncements", bot.get_cog("NtustAnnouncements"))
    assert cog.tasks == ()  # no channel: nothing is requested
    boards = bundled()["boards"]
    assert [(board["name"], board["board"]) for board in boards[: len(SCRAPED)]] == SCRAPED
    assert boards[5]["title-prefix"] == MAIN_OFFICE
    assert {board["channel-id"] for board in boards} == {0}
    assert len(boards) > len(SCRAPED)  # the units that the scraper did not read


@pytest.mark.parametrize(
    ("change", "error"),
    [
        pytest.param(
            "poll-interval: 29",
            "poll-interval: Input should be greater than or equal to 30",
            id="a short interval",
        ),
        pytest.param(
            "rendition-wait: 86401",
            "rendition-wait: Input should be less than or equal to 86400",
            id="a long wait",
        ),
        pytest.param(
            "rendition-wait: yes", "rendition-wait: Input should be a valid integer", id="yes"
        ),
        pytest.param(
            'api-url: "https://bulletin.ntust.org/api/v1?token=x"',
            "api-url: Value error, must be an http or https URL",
            id="a query",
        ),
        pytest.param(
            'api-url: "https:///api/v1"',
            "api-url: Value error, must be an http or https URL",
            id="no host",
        ),
        pytest.param(
            'api-url: "https://user@bulletin.ntust.org/api/v1"',
            "api-url: Value error, must be an http or https URL",
            id="user info",
        ),
        pytest.param(
            'api-url: "ftp://bulletin.ntust.org/api/v1"',
            "api-url: Value error, must be an http or https URL",
            id="another scheme",
        ),
        pytest.param(
            'api-url: "https://[::1/api"',
            "api-url: Value error, must be an http or https URL",
            id="unreadable",
        ),
        pytest.param("boards: []", "boards: Value error, list at least one board", id="no boards"),
    ],
)
def test_invalid_values(change: str, error: str) -> None:
    """Requirement: The config names the feed and the boards."""
    with pytest.raises(ConfigError) as raised:
        parse(f"{change}\n{BOARDS}" if not change.startswith("boards") else change)

    assert error in str(raised.value)


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        ('board: "1053-1436"', 'board: "1053-"', "boards.0.board: String should match pattern"),
        ('board: "1053-1436"', 'board: "x"', "boards.0.board: String should match pattern"),
        (
            "channel-id: 101",
            "channel-id: -1",
            "boards.0.channel-id: Input should be greater than or equal to 0",
        ),
        (
            "name: STUDENT_AFFAIRS",
            "name: STUDENT_DORMITORY",
            "boards: Value error, two boards are named STUDENT_DORMITORY",
        ),
    ],
)
def test_invalid_boards(old: str, new: str, error: str) -> None:
    """Requirement: The config names the feed and the boards."""
    assert old in BOARDS

    with pytest.raises(ConfigError) as raised:
        parse(BOARDS.replace(old, new, 1))

    assert error in str(raised.value)
