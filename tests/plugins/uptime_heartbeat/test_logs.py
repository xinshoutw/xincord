"""What the logs show of a URL: its origin, without the push token.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:99-123
"""

import pytest

from xincord.plugins.uptime_heartbeat.logs import origin, redact

ORIGIN_ONLY = "Logs show only the URL's origin"
# A URL with a quote in its path: Python's repr, which aiohttp's texts use, then quotes it with ".
QUOTED = "https://status.example.com/api/push/it's?ping=42"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=ORIGIN_ONLY)
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param(
            "https://status.example.com/api/push/xxxxxxxxxx?status=up&msg=OK&ping=%ping%",
            "https://status.example.com",
            id="path and query",
        ),
        pytest.param(
            "http://127.0.0.1:3001/api/push/x?ping=%ping%", "http://127.0.0.1:3001", id="port"
        ),
        pytest.param("HTTPS://[::1]:3001/api/push/x", "https://[::1]:3001", id="IPv6"),
        pytest.param(
            "https://user:secret@status.example.com:8443/api/push/x",
            "https://status.example.com:8443",
            id="user info",
        ),
        pytest.param(
            "https://status.example.com?token=x", "https://status.example.com", id="query"
        ),
        pytest.param("https://status.example.com#x", "https://status.example.com", id="fragment"),
        pytest.param("https://status.example.com", "https://status.example.com", id="origin"),
        pytest.param(
            "https://status.example.com:%ping%/push",
            "https://status.example.com:%ping%",
            id="ping as the port",
        ),
    ],
)
def test_origin(url: str, expected: str) -> None:
    """Requirement: Logs show only the URL's origin."""
    assert origin(url) == expected


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=ORIGIN_ONLY)
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(
            # aiohttp 3.14.4's connect timeout names the whole URL.
            "Connection timeout to host https://status.example.com/api/push/xxxxxxxxxx?ping=42",
            "Connection timeout to host https://status.example.com",
            id="connect timeout",
        ),
        pytest.param(
            # aiohttp 3.14.4's error for a malformed answer ends with the URL in quotes.
            "400, message='Bad status line', url='https://status.example.com/api/push/x?ping=42'",
            "400, message='Bad status line', url='https://status.example.com'",
            id="malformed answer",
        ),
        pytest.param(f"url={QUOTED!r}", 'url="https://status.example.com"', id="quote in the path"),
        pytest.param(
            "Cannot connect to host status.example.com:443 ssl:default [Connection refused]",
            "Cannot connect to host status.example.com:443 ssl:default [Connection refused]",
            id="no URL",
        ),
        pytest.param(
            "from HTTP://user:pw@a.example.com:81/x to https://b.example.com/y?z=1 at once",
            "from http://a.example.com:81 to https://b.example.com at once",
            id="two URLs",
        ),
    ],
)
def test_redact(text: str, expected: str) -> None:
    """Requirement: Logs show only the URL's origin."""
    assert redact(text) == expected
