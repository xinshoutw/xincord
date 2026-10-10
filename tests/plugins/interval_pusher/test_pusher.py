"""One listener's loop, driven by fakes for the monitor, Discord and the clock.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:15-136
"""

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import aiohttp
import discord
import pytest

from xincord.plugins.interval_pusher.config import Listener
from xincord.plugins.interval_pusher.pusher import Pusher, build_url, rest_ping

if TYPE_CHECKING:
    from discord.http import Route

URL = "https://status.example.com/api/push/xxxxxxxxxx?status=up&msg=OK&ping=%ping%"
PUSHED = URL.replace("%ping%", "42")


@dataclass
class Fakes:
    """Stand in for the monitor and Discord's REST ping; record what the loop asks for, in order.

    The monitor answers the pushes with ``answers`` in turn, repeating the last one; an exception
    is raised instead.
    """

    answers: tuple[int | Exception, ...] = (200,)
    ping_ms: int | Exception = 42
    calls: list[str] = field(default_factory=list[str])
    pushes: int = 0

    async def get(self, url: str) -> int:
        self.calls.append(f"get {url}")
        answer = self.answers[min(self.pushes, len(self.answers) - 1)]
        self.pushes += 1
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def ping(self) -> int:
        self.calls.append("ping")
        if isinstance(self.ping_ms, Exception):
            raise self.ping_ms
        return self.ping_ms

    async def sleep(self, seconds: float) -> None:
        self.calls.append(f"sleep {seconds}")

    def pusher(self, url: str = URL, interval: int = 60) -> Pusher:
        """Listener 1, pushing ``url`` every ``interval`` seconds through these fakes."""
        listener = Listener(url=url, interval=interval)
        return Pusher(1, listener, get=self.get, ping=self.ping, sleep=self.sleep)


def test_every_placeholder_is_replaced() -> None:
    """Requirement: The URL carries the REST ping."""
    template = "https://status.example.com/%ping%/push?ping=%ping%"

    assert build_url(template, 42) == "https://status.example.com/42/push?ping=42"
    assert build_url(template, -1) == "https://status.example.com/-1/push?ping=-1"


async def test_ping_in_the_url() -> None:
    """Requirement: The URL carries the REST ping."""
    fakes = Fakes(ping_ms=42)

    url = await fakes.pusher("https://status.example.com/%ping%/push?ping=%ping%").url()

    assert url == "https://status.example.com/42/push?ping=42"
    assert fakes.calls == ["ping"]


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(aiohttp.ClientConnectionError("Connection reset by peer"), id="network"),
        pytest.param(discord.DiscordException("Discord is unavailable"), id="Discord"),
    ],
)
async def test_failed_ping(error: Exception, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The URL carries the REST ping."""
    fakes = Fakes(ping_ms=error)

    with caplog.at_level(logging.WARNING):
        url = await fakes.pusher().url()

    assert url == URL.replace("%ping%", "-1")
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage().startswith(
        "IntervalPusher listener 1 could not measure the REST ping, so %ping% is -1: "
    )


async def test_no_placeholder() -> None:
    """Requirement: The URL carries the REST ping."""
    fakes = Fakes()
    plain = "https://status.example.com/api/push/xxxxxxxxxx?status=up"

    assert await fakes.pusher(plain).url() == plain
    assert fakes.calls == []  # v3 asked Discord at every push


async def test_measured_round_trip() -> None:
    """Requirement: The URL carries the REST ping."""
    requests: list[Route] = []
    times = iter([100.0, 100.0424])

    async def request(route: Route) -> object:
        requests.append(route)
        return {"id": "1"}

    client = cast("discord.Client", SimpleNamespace(http=SimpleNamespace(request=request)))

    assert await rest_ping(client, clock=lambda: next(times)) == 42
    assert [(route.method, route.path) for route in requests] == [("GET", "/users/@me")]


STATUS = "The status code decides what follows"


def records_above(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno > level]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=STATUS)
@pytest.mark.parametrize("status", [200, 204, 299])
async def test_success(status: int, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    with caplog.at_level(logging.DEBUG, "xincord.plugins.interval_pusher"):
        keep_pushing = await Fakes(answers=(status,)).pusher().push()

    assert keep_pushing
    assert records_above(caplog, logging.DEBUG) == []
    assert f"IntervalPusher listener 1 pushed {PUSHED}" in caplog.messages


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=STATUS)
async def test_not_found(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    keep_pushing = await Fakes(answers=(404,)).pusher().push()

    assert not keep_pushing  # until the plugin reloads or the bot restarts
    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.WARNING
    assert record.getMessage() == (
        "IntervalPusher listener 1 stopped: the status monitor refused the push (code 404)"
    )


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=STATUS)
async def test_monitor_offline(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    keep_pushing = await Fakes(answers=(521,)).pusher().push()

    assert keep_pushing
    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.WARNING
    assert record.getMessage() == (
        "IntervalPusher listener 1: the status monitor is offline (code 521)"
    )


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=STATUS)
@pytest.mark.parametrize("status", [500, 302, 401])
async def test_other_status(status: int, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    keep_pushing = await Fakes(answers=(status,)).pusher().push()

    assert keep_pushing
    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.ERROR
    assert record.getMessage() == (
        f"IntervalPusher listener 1: pushing to {PUSHED} failed with code {status}"
    )


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=STATUS)
@pytest.mark.parametrize(
    ("error", "text"),
    [
        pytest.param(
            aiohttp.ClientConnectionError("Cannot connect to host status.example.com:443"),
            "Cannot connect to host status.example.com:443",
            id="network",
        ),
        pytest.param(TimeoutError(), "TimeoutError", id="timeout"),
        pytest.param(ConnectionRefusedError("Connection refused"), "Connection refused", id="os"),
    ],
)
async def test_network_error(error: Exception, text: str, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    keep_pushing = await Fakes(answers=(error,)).pusher().push()

    assert keep_pushing
    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.ERROR
    # The URL as configured, as v3 logged it; no traceback for a network error.
    assert record.getMessage() == f"IntervalPusher listener 1: pushing to {URL} failed: {text}"
    assert record.exc_info is None


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=STATUS)
async def test_unexpected_error(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    keep_pushing = await Fakes(answers=(ValueError("unexpected"),)).pusher().push()

    assert keep_pushing
    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.ERROR
    assert record.getMessage() == f"IntervalPusher listener 1: pushing to {URL} failed: unexpected"
    assert record.exc_info is not None  # the traceback, for a failure nobody expected
