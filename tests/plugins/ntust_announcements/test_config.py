"""The NtustAnnouncements config: v3's keys and the boards that v3 hard-coded.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/config/ConfigSerializer.kt:6-26
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:220-238
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:21-115
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/resources/config.yaml:1-105
"""

import json
import logging
from importlib.resources import files
from typing import TYPE_CHECKING, Any, cast

import pytest
import yaml

from plugin_fakes import golden, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.ntust_announcements.cog import NtustAnnouncements

GOLDEN = golden("ntust_announcements")
EXAMPLE_KEY = "sk-thisisatestkey1234567890abcdef1234567890"  # v3's placeholder, refused as in v3
BOARDS = """\
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
VALID = f"""\
fetch-interval: 3600
api-keys:
  - "first-key"
prompt: "{{{{page_url}}}} {{{{base_url}}}} {{{{now}}}} {{{{html}}}}"
model: "gemini-2.5-flash"
{BOARDS}"""


def bundled() -> dict[str, Any]:
    """The bundled config.yaml, parsed."""
    text = files("xincord.plugins.ntust_announcements").joinpath("config.yaml").read_text("utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    return data


def v3_file() -> str:
    """v3's config.yaml with an operator's keys, as `migrate_v3` moves it, and `boards` added."""
    prompt = json.dumps(bundled()["prompt"], ensure_ascii=False)  # the bundled prompt is v3's
    return (
        "enabled: true\n\nfetch-interval: 3600\napi-keys:\n"
        '  - "first-key"\n  - "second-key"\n\n'
        f"prompt: {prompt}\n{BOARDS}"
    )


async def test_v3_config_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the boards, the Gemini keys and the prompt."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=v3_file())

    assert bot.loaded == ("NtustAnnouncements",)
    assert "unknown key enabled" in caplog.text
    for key in ("fetch-interval", "api-keys", "prompt", "boards", "model"):
        assert f"unknown key {key}" not in caplog.text
    config = cast("NtustAnnouncements", bot.get_cog("NtustAnnouncements")).config
    assert config.fetch_interval == 3600
    assert config.api_keys == ("first-key", "second-key")
    assert config.prompt == bundled()["prompt"]
    assert config.model == "gemini-2.5-flash"  # v3's model, the default
    assert [(board.name, board.channel_id, board.title_prefix) for board in config.boards] == [
        ("STUDENT_DORMITORY", 101, ""),
        ("LANGUAGE_CENTER_RECRUITMENT", 102, ""),
    ]


async def test_bundled_config(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the boards, the Gemini keys and the prompt."""
    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store)

    assert bot.loaded == ()
    for number in (0, 1):  # v3's two example keys
        assert (
            f"api-keys.{number}: Value error, replace the example key with a Gemini API key"
            in caplog.text
        )
    for number in range(18):
        assert f"boards.{number}.channel-id: Input should be greater than 0" in caplog.text
    boards = [
        {key: value for key, value in board.items() if key != "channel-id"}
        for board in bundled()["boards"]
    ]
    assert boards == GOLDEN["bundled_boards"]  # v3's 18 boards in v3's order
    assert bundled()["fetch-interval"] == 3600
    assert bundled()["model"] == "gemini-2.5-flash"


@pytest.mark.parametrize(
    ("change", "error"),
    [
        pytest.param(
            ("fetch-interval: 3600", "fetch-interval: 59"),
            "fetch-interval: Input should be greater than or equal to 60",
            id="interval below 60",
        ),
        pytest.param(
            # v3's Long held no more.
            ("fetch-interval: 3600", "fetch-interval: 9223372036854775808"),
            "fetch-interval: Input should be less than or equal to 9223372036854775807",
            id="interval beyond a Long",
        ),
        pytest.param(
            ('  - "first-key"', '  - "first-key"\n  - "  "'),
            "api-keys.1: Value error, must not be blank",
            id="blank key",
        ),
        pytest.param(
            ('  - "first-key"', f'  - "{EXAMPLE_KEY}"'),
            "api-keys.0: Value error, replace the example key with a Gemini API key",
            id="example key",
        ),
        pytest.param(
            ('api-keys:\n  - "first-key"', "api-keys: []"),
            "api-keys: Tuple should have at least 1 item after validation, not 0",
            id="no keys",
        ),
        pytest.param(
            (" {{html}}", ""),
            "prompt: Value error, the prompt lacks {{html}}",
            id="prompt without html",
        ),
        pytest.param(
            ('"{{page_url}} {{base_url}} {{now}} {{html}}"', '"{{page_title}}"'),
            "prompt: Value error, the prompt lacks {{page_url}}, {{base_url}}, {{now}}, {{html}}",
            id="prompt without tokens",
        ),
        pytest.param(
            ("layout: language-center", "layout: library"),
            "boards.1.layout: Input should be 'student-affairs', 'academic-affairs' or "
            "'language-center'",
            id="unknown layout",
        ),
        pytest.param(
            ("name: LANGUAGE_CENTER_RECRUITMENT", "name: STUDENT_DORMITORY"),
            "boards: Value error, two boards are named STUDENT_DORMITORY",
            id="same name",
        ),
        pytest.param(
            ("name: LANGUAGE_CENTER_RECRUITMENT", 'name: " "'),
            "boards.1.name: String should match pattern",
            id="blank name",
        ),
        pytest.param(
            (
                'url: "https://lc.ntust.edu.tw/p/403-1070-1626-1.php"',
                'url: "lc.ntust.edu.tw/p/403-1070-1626-1.php"',
            ),
            "boards.1.url: Value error, must be an http or https URL with a host and no spaces",
            id="URL without a host",
        ),
        pytest.param(
            (
                'url: "https://lc.ntust.edu.tw/p/403-1070-1626-1.php"',
                'url: "https://lc.ntust.edu.tw:99999/p/403-1070-1626-1.php"',
            ),
            "boards.1.url: Value error, must be an http or https URL with a host and no spaces",
            id="URL with an invalid port",
        ),
        pytest.param(
            ("channel-id: 102", "channel-id: general"),
            "boards.1.channel-id: Input should be a valid integer",
            id="channel by name",
        ),
        pytest.param(
            ('model: "gemini-2.5-flash"', 'model: "gemini/../flash"'),
            "model: String should match pattern",
            id="model with a slash",
        ),
        pytest.param(
            (BOARDS, "boards: []\n"),
            "boards: Tuple should have at least 1 item after validation, not 0",
            id="no boards",
        ),
    ],
)
async def test_invalid_values(
    change: tuple[str, str],
    error: str,
    tmp_path: Path,
    store: Store,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: The config names the boards, the Gemini keys and the prompt."""
    old, new = change
    assert old in VALID
    config = VALID.replace(old, new, 1)

    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert error in caplog.text


@pytest.mark.parametrize(
    "keys",
    [
        pytest.param('"first-secret-key"', id="a key instead of a list"),
        pytest.param('["first-secret-key", ""]', id="a blank key beside a real one"),
        pytest.param('["first-secret-key", 7]', id="a number beside a real one"),
    ],
)
async def test_keys_stay_hidden(
    keys: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the boards, the Gemini keys and the prompt."""
    config = VALID.replace('api-keys:\n  - "first-key"', f"api-keys: {keys}")

    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert "api-keys" in caplog.text  # the error names the key, with its traceback logged
    assert "first-secret-key" not in caplog.text
