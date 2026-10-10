"""What the logs show: a URL's origin without the push token, and failures when they are new.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:99-123
"""

import pytest

from xincord.plugins.uptime_heartbeat.logs import Failures, origin, private_parts, redact

# A URL with a quote in its path: Python's repr, which aiohttp's texts use, then quotes it with ".
QUOTED = "https://status.example.com/api/push/it's?ping=42"


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


@pytest.mark.parametrize(
    ("url", "parts"),
    [
        pytest.param(
            "https://user:pw@status.example.com:8443/api/push/x?status=up#top",
            (
                "/api/push/x?status=up#top",
                "/api/push/x?status=up",
                "/api/push/x",
                "status=up",
                "user:pw",
                "top",
            ),
            id="every part",
        ),
        pytest.param("https://status.example.com", (), id="origin only"),
        pytest.param(
            # As written and as aiohttp sends it, encoded by yarl.
            f"https://status.example.com/caf{chr(0xE9)}",
            ("/caf%C3%A9", f"/caf{chr(0xE9)}"),
            id="encoded",
        ),
        pytest.param(
            # yarl refuses this port: the parts as written.
            "https://status.example.com:%ping%/push?ping=%ping%",
            ("/push?ping=%ping%", "ping=%ping%", "/push"),
            id="URL that yarl refuses",
        ),
    ],
)
def test_private_parts(url: str, parts: tuple[str, ...]) -> None:
    """Requirement: Logs show only the URL's origin."""
    assert private_parts(url) == parts


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(
            # aiohttp's parser quotes the bad status line, here the request line sent back.
            "400, message=\"Bad status line: b'GET /api/push/xxxxxxxxxx?status=up HTTP/1.1'\", "
            "url='http://127.0.0.1:3001/api/push/xxxxxxxxxx?status=up'",
            "400, message=\"Bad status line: b'GET ... HTTP/1.1'\", url='http://127.0.0.1:3001'",
            id="request line",
        ),
        pytest.param(
            "Server disconnected: Location: /api/push/xxxxxxxxxx",
            "Server disconnected: Location: ...",
            id="path alone",
        ),
    ],
)
def test_redact_the_urls_private_parts(text: str, expected: str) -> None:
    """Requirement: Logs show only the URL's origin."""
    url = "http://127.0.0.1:3001/api/push/xxxxxxxxxx?status=up"

    assert redact(text, url) == expected


def test_kinds_are_new_once_per_episode() -> None:
    """Requirement: A failure is logged when it starts, changes or ends."""
    failures = Failures()
    kinds = (500, 500, 502, 504, 502, 504, TimeoutError)

    assert [failures.fail(kind) for kind in kinds] == [True, False, True, True, False, False, True]
    assert failures.count == len(kinds)


def test_episode_ends_after_three_successes() -> None:
    """Requirement: A failure is logged when it starts, changes or ends."""
    failures = Failures()

    assert failures.succeed() == 0  # no episode
    failures.fail(500)
    failures.fail(500)
    assert [failures.succeed() for _ in range(3)] == [0, 0, 2]
    assert failures.fail(500)  # new again: another episode


def test_failure_before_three_successes_continues_the_episode() -> None:
    """Requirement: A failure is logged when it starts, changes or ends."""
    failures = Failures()
    failures.fail(500)

    assert [failures.succeed() for _ in range(2)] == [0, 0]
    assert not failures.fail(500)  # the same episode
    assert [failures.succeed() for _ in range(3)] == [0, 0, 2]
