"""The NtustAnnouncements config: v3's keys, and the boards and model settings that v3 hard-coded.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/config/ConfigSerializer.kt:6-26
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:220-238
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:21-115
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/resources/config.yaml:1-105
"""

import json
import logging
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import yaml

from plugin_fakes import golden, load_plugin
from xincord.core.config import ConfigError, parse_model
from xincord.plugins.ntust_announcements.api import Api, ApiFormat
from xincord.plugins.ntust_announcements.config import Config, bundled_review_prompt
from xincord.plugins.ntust_announcements.conversion import Limits

if TYPE_CHECKING:
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


# Every model setting at v3's value, written out.
EXPLICIT = """\
api-format: gemini
endpoint: "https://generativelanguage.googleapis.com/v1beta"
model: "gemini-2.5-flash"
temperature: 0.1
max-output-tokens: null
request-timeout: 300
connect-timeout: 30
rate-limit: 10
rate-window: 60
max-attempts: 10
retry-waits: [60, 300, 900, 1800]
"""
SETTINGS = """\
api-format: openai
endpoint: "https://openrouter.ai/api/v1/"
model: "openai/gpt-4o-mini"
temperature: null
max-output-tokens: 2048
request-timeout: 120
connect-timeout: 10
rate-limit: 3
rate-window: 30.5
max-attempts: 4
retry-waits: [5, 10]
"""
DEFAULTS = yaml.safe_load(EXPLICIT)


def with_settings(settings: str) -> str:
    """``VALID`` with ``settings`` in place of its ``model`` line."""
    old = 'model: "gemini-2.5-flash"\n'
    assert old in VALID
    return VALID.replace(old, settings)


def parse(text: str) -> Config:
    """``text`` as the plugin's ``config.yaml``, through the core's validation.

    Raises:
        ConfigError: The text is not a valid config.
    """
    return parse_model(Path("config.yaml"), yaml.safe_load(text), Config)


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
    """Requirement: The config names the boards, the API keys and the prompt."""
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
    """Requirement: The config names the boards, the API keys and the prompt."""
    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store)

    assert bot.loaded == ()
    for number in (0, 1):  # v3's two example keys
        assert (
            f"api-keys.{number}: Value error, replace the example key with your API key"
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
            "api-keys.0: Value error, replace the example key with your API key",
            id="example key",
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
            "model: Value error, the gemini format takes letters, digits, '.', '-' and '_'",
            id="model with a slash",
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
    """Requirement: The config names the boards, the API keys and the prompt."""
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
    """Requirement: The config names the boards, the API keys and the prompt."""
    config = VALID.replace('api-keys:\n  - "first-key"', f"api-keys: {keys}")

    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert "api-keys" in caplog.text  # the error names the key, with its traceback logged
    assert "first-secret-key" not in caplog.text


@pytest.mark.parametrize(
    ("change", "error"),
    [
        pytest.param(
            ('api-keys:\n  - "first-key"', "api-keys: []"),
            "api-keys: Value error, list at least one key",
            id="no keys",
        ),
        pytest.param(
            (BOARDS, "boards: []\n"), "boards: Value error, list at least one board", id="no boards"
        ),
    ],
)
async def test_empty_lists(
    change: tuple[str, str],
    error: str,
    tmp_path: Path,
    store: Store,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: The config names the boards, the API keys and the prompt."""
    old, new = change
    config = VALID.replace(old, new, 1)

    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert error in caplog.text


async def test_errors_name_the_invalid_items(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the boards, the API keys and the prompt."""
    await load_plugin("NtustAnnouncements", tmp_path / "plugins", store)

    # pydantic's length check counts the items that validated: 18 invalid boards are no empty list.
    assert "at least 1 item" not in caplog.text
    assert "boards.17.channel-id" in caplog.text


async def test_default_model_settings(tmp_path: Path, store: Store) -> None:
    """Requirement: The model settings are config."""
    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=v3_file())
    config = cast("NtustAnnouncements", bot.get_cog("NtustAnnouncements")).config

    # v3's API, model, temperature, timeouts (300 and 30 seconds), rate limit and retries.
    assert config.api == Api(
        ApiFormat.GEMINI,
        "https://generativelanguage.googleapis.com/v1beta",
        "gemini-2.5-flash",
        0.1,
        None,
        300,
        30,
    )
    assert config.limits == Limits(10, 60, 10, (60, 300, 900, 1800))


def test_bundled_model_settings() -> None:
    """Requirement: The model settings are config."""
    data = bundled()
    keys = data | {
        "api-keys": ["key-one"],
        "boards": [board | {"channel-id": 101} for board in data["boards"]],
    }

    config = parse_model(Path("config.yaml"), keys, Config)

    assert (config.api, config.limits) == (Api(), Limits())
    assert {key: data.get(key, "missing") for key in DEFAULTS} == DEFAULTS


def test_model_settings_from_the_file() -> None:
    """Requirement: The model settings are config."""
    config = parse(with_settings(SETTINGS))

    assert config.api == Api(
        ApiFormat.OPENAI,
        "https://openrouter.ai/api/v1",  # without the final slash
        "openai/gpt-4o-mini",
        None,
        2048,
        120,
        10,
    )
    assert config.limits == Limits(3, 30.5, 4, (5, 10))


ENDPOINT_ERROR = (
    "endpoint: Value error, must be an http or https URL with a host, without user info, a query "
    "or a fragment"
)


@pytest.mark.parametrize(
    ("change", "error"),
    [
        pytest.param(
            ("api-format: gemini", "api-format: claude"),
            "api-format: Input should be 'gemini' or 'openai'",
            id="unknown format",
        ),
        *(
            pytest.param(
                (
                    'endpoint: "https://generativelanguage.googleapis.com/v1beta"',
                    f'endpoint: "{endpoint}"',
                ),
                ENDPOINT_ERROR,
                id=name,
            )
            for name, endpoint in (
                ("endpoint with another scheme", "ftp://api.example.com/v1"),
                ("endpoint without a host", "https:///v1"),
                ("endpoint with user info", "https://user:password@api.example.com/v1"),
                ("endpoint with a query", "https://api.example.com/v1?alt=json"),
                ("endpoint with an empty query", "https://api.example.com/v1?"),
                ("endpoint with a fragment", "https://api.example.com/v1#top"),
                ("endpoint with a space", "https://api.example.com/v 1"),
                ("endpoint with an invalid port", "https://api.example.com:99999/v1"),
                ("endpoint without a scheme", "api.example.com/v1"),
            )
        ),
        pytest.param(
            ('endpoint: "https://generativelanguage.googleapis.com/v1beta"', "endpoint: 7"),
            "endpoint: Input should be a valid string",
            id="endpoint not a string",
        ),
        pytest.param(
            ('model: "gemini-2.5-flash"', 'model: "models/gemini-2.5-flash"'),
            "model: Value error, the gemini format takes letters, digits, '.', '-' and '_'",
            id="gemini model with a slash",
        ),
        pytest.param(
            ('model: "gemini-2.5-flash"', 'model: " "'),
            "model: Value error, must be 1 to 256 characters without whitespace",
            id="blank model",
        ),
        pytest.param(
            ("api-format: gemini", "api-format: openai"),
            None,  # see below: a long model
            id="openai model too long",
        ),
        pytest.param(
            ("temperature: 0.1", "temperature: 2.5"),
            "temperature: Input should be less than or equal to 2",
            id="temperature above 2",
        ),
        pytest.param(
            ("temperature: 0.1", "temperature: -0.1"),
            "temperature: Input should be greater than or equal to 0",
            id="negative temperature",
        ),
        pytest.param(
            ("temperature: 0.1", "temperature: .nan"),
            "temperature: Input should be a finite number",
            id="temperature not a number",
        ),
        pytest.param(
            ("temperature: 0.1", "temperature: warm"),
            "temperature: Input should be a valid number",
            id="temperature as text",
        ),
        pytest.param(
            ("max-output-tokens: null", "max-output-tokens: 0"),
            "max-output-tokens: Input should be greater than or equal to 1",
            id="no output",
        ),
        pytest.param(
            ("max-output-tokens: null", "max-output-tokens: 1048577"),
            "max-output-tokens: Input should be less than or equal to 1048576",
            id="output beyond the bound",
        ),
        pytest.param(
            ("max-output-tokens: null", "max-output-tokens: 1.5"),
            "max-output-tokens: Input should be a valid integer",
            id="fractional output",
        ),
        pytest.param(
            ("request-timeout: 300", "request-timeout: 0"),
            "request-timeout: Input should be greater than 0",
            id="no request time",
        ),
        pytest.param(
            ("request-timeout: 300", "request-timeout: 3601"),
            "request-timeout: Input should be less than or equal to 3600",
            id="request time beyond an hour",
        ),
        pytest.param(
            ("request-timeout: 300", "request-timeout: .inf"),
            "request-timeout: Input should be a finite number",
            id="endless request time",
        ),
        pytest.param(
            ("connect-timeout: 30", "connect-timeout: 0"),
            "connect-timeout: Input should be greater than 0",
            id="no connect time",
        ),
        pytest.param(
            ("connect-timeout: 30", "connect-timeout: 301"),
            "connect-timeout: Value error, must not exceed request-timeout",
            id="connect time over the request time",
        ),
        pytest.param(
            ("rate-limit: 10", "rate-limit: 0"),
            "rate-limit: Input should be greater than or equal to 1",
            id="no attempt per window",
        ),
        pytest.param(
            ("rate-limit: 10", "rate-limit: 10001"),
            "rate-limit: Input should be less than or equal to 10000",
            id="rate limit beyond the bound",
        ),
        pytest.param(
            ("rate-window: 60", "rate-window: 0"),
            "rate-window: Input should be greater than 0",
            id="empty window",
        ),
        pytest.param(
            ("rate-window: 60", "rate-window: 86401"),
            "rate-window: Input should be less than or equal to 86400",
            id="window beyond a day",
        ),
        pytest.param(
            ("max-attempts: 10", "max-attempts: 0"),
            "max-attempts: Input should be greater than or equal to 1",
            id="no attempt",
        ),
        pytest.param(
            ("max-attempts: 10", "max-attempts: 101"),
            "max-attempts: Input should be less than or equal to 100",
            id="attempts beyond the bound",
        ),
        pytest.param(
            ("retry-waits: [60, 300, 900, 1800]", "retry-waits: []"),
            "retry-waits: Value error, list at least one wait",
            id="no waits",
        ),
        pytest.param(
            ("retry-waits: [60, 300, 900, 1800]", "retry-waits: [60, -1]"),
            "retry-waits.1: Input should be greater than or equal to 0",
            id="negative wait",
        ),
        pytest.param(
            ("retry-waits: [60, 300, 900, 1800]", "retry-waits: [60, 86401]"),
            "retry-waits.1: Input should be less than or equal to 86400",
            id="wait beyond a day",
        ),
        pytest.param(
            ("retry-waits: [60, 300, 900, 1800]", "retry-waits: 60"),
            "retry-waits: Input should be a valid tuple",
            id="one wait without a list",
        ),
        pytest.param(
            ("retry-waits: [60, 300, 900, 1800]", f"retry-waits: {[1] * 101}"),
            "retry-waits: Tuple should have at most 100 items after validation, not 101",
            id="too many waits",
        ),
    ],
)
def test_invalid_model_settings(change: tuple[str, str], error: str | None) -> None:
    """Requirement: The model settings are config."""
    old, new = change
    text = with_settings(EXPLICIT)
    assert old in text
    text = text.replace(old, new, 1)
    if error is None:  # an openai model may hold "/" and ":", but no more than 256 characters
        assert parse(text.replace('model: "gemini-2.5-flash"', 'model: "a/b:c"')).model == "a/b:c"
        text = text.replace('model: "gemini-2.5-flash"', f'model: "{"m" * 257}"')
        error = "model: Value error, must be 1 to 256 characters without whitespace"

    with pytest.raises(ConfigError) as raised:
        parse(text)

    [line] = str(raised.value).splitlines()  # one problem, the key named
    assert line.startswith(f"config.yaml: {error}")


@pytest.mark.parametrize(
    "endpoint",
    [
        pytest.param("https://user:secret-password@api.example.com/v1", id="password"),
        pytest.param("https://api.example.com/secret-token/v1?key=secret-key", id="path and query"),
        pytest.param("ftp://secret-host.example.com/secret-token", id="another scheme"),
        pytest.param("https://api.example.com:99999/secret-token", id="invalid port"),
    ],
)
def test_endpoint_stays_hidden(endpoint: str) -> None:
    """Requirement: The model settings are config."""
    text = with_settings(EXPLICIT).replace(
        'endpoint: "https://generativelanguage.googleapis.com/v1beta"',
        f'endpoint: "{endpoint}"',
    )

    with pytest.raises(ConfigError) as raised:
        parse(text)

    assert str(raised.value) == f"config.yaml: {ENDPOINT_ERROR}"
    assert "secret" not in str(raised.value.__cause__)


@pytest.mark.parametrize("api_format", ["gemini", "openai"])
def test_example_key(api_format: str) -> None:
    """Requirement: The config names the boards, the API keys and the prompt."""
    text = with_settings(f'api-format: {api_format}\nmodel: "gpt-4o-mini"\n').replace(
        '  - "first-key"', f'  - "{EXAMPLE_KEY}"'
    )

    with pytest.raises(ConfigError) as raised:
        parse(text)

    # v3's example key, whatever the format, and no product named.
    assert str(raised.value) == (
        "config.yaml: api-keys.0: Value error, replace the example key with your API key"
    )


@pytest.mark.parametrize(
    ("change", "error"),
    [
        pytest.param(
            ("temperature: 0.1", "temperature: off"),
            "temperature: Input should be a valid number",
            id="temperature",
        ),
        pytest.param(
            ("max-output-tokens: null", "max-output-tokens: yes"),
            "max-output-tokens: Input should be a valid integer",
            id="max-output-tokens",
        ),
        pytest.param(
            ("request-timeout: 300", "request-timeout: true"),
            "request-timeout: Input should be a valid number",
            id="request-timeout",
        ),
        pytest.param(
            ("connect-timeout: 30", "connect-timeout: true"),
            "connect-timeout: Input should be a valid number",
            id="connect-timeout",
        ),
        pytest.param(
            ("rate-limit: 10", "rate-limit: on"),
            "rate-limit: Input should be a valid integer",
            id="rate-limit",
        ),
        pytest.param(
            ("rate-window: 60", "rate-window: true"),
            "rate-window: Input should be a valid number",
            id="rate-window",
        ),
        pytest.param(
            ("max-attempts: 10", "max-attempts: true"),
            "max-attempts: Input should be a valid integer",
            id="max-attempts",
        ),
        pytest.param(
            ("retry-waits: [60, 300, 900, 1800]", "retry-waits: [60, yes]"),
            "retry-waits.1: Input should be a valid number",
            id="retry-waits",
        ),
    ],
)
def test_booleans_are_no_numbers(change: tuple[str, str], error: str) -> None:
    """Requirement: The model settings are config."""
    # YAML reads yes, on and true as true, which a lax number would take as 1.
    old, new = change
    text = with_settings(EXPLICIT)
    assert old in text

    with pytest.raises(ConfigError) as raised:
        parse(text.replace(old, new, 1))

    [line] = str(raised.value).splitlines()
    assert line.startswith(f"config.yaml: {error}")


@pytest.mark.parametrize(
    "endpoint",
    [
        pytest.param("https://api.example.com\\secret-token/v1", id="backslash"),
        pytest.param("https://api.example.com:0/v1", id="port 0"),
    ],
)
def test_endpoints_as_requests_read_them(endpoint: str) -> None:
    """Requirement: The model settings are config."""
    # aiohttp's URLs (yarl) refuse a backslash in the authority, and port 0 reaches no server.
    text = with_settings(EXPLICIT).replace(
        'endpoint: "https://generativelanguage.googleapis.com/v1beta"', f"endpoint: '{endpoint}'"
    )

    with pytest.raises(ConfigError) as raised:
        parse(text)

    assert str(raised.value) == f"config.yaml: {ENDPOINT_ERROR}"
    assert "secret" not in str(raised.value.__cause__)


@pytest.mark.xfail(strict=True, reason="Answers that hold a refused text are retried")
def test_reject_texts() -> None:
    """Requirement: Answers that hold a refused text are retried."""
    assert parse(VALID).reject_texts == ("```",)
    assert parse(VALID + "reject-texts: []\n").reject_texts == ()

    with pytest.raises(ConfigError) as raised:
        parse(VALID + 'reject-texts: ["```", ""]\n')

    assert "reject-texts.1: String should have at least 1 character" in str(raised.value)


@pytest.mark.xfail(strict=True, reason="The review prompt")
def test_review_prompt() -> None:
    """Requirement: The review prompt."""
    bundled_prompt = bundled()["review-prompt"]

    assert parse(VALID).review_prompt is None  # the bundled one is used
    assert bundled_review_prompt() == bundled_prompt
    assert "{{html}}" in bundled_prompt
    assert "{{markdown}}" in bundled_prompt
    assert parse(VALID).reviewers == ()
    assert parse(VALID + "reviewers: [7, 8]\n").reviewers == (7, 8)

    with pytest.raises(ConfigError) as raised:
        parse(VALID + 'review-prompt: "check {{html}}"\n')

    assert "review-prompt: Value error, the review prompt lacks {{markdown}}" in str(raised.value)
