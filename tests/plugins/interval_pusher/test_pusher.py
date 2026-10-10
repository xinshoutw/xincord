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

PING = "The URL carries the REST ping"
URL = "https://status.example.com/api/push/xxxxxxxxxx?status=up&msg=OK&ping=%ping%"


@dataclass
class Fakes:
    """Stand in for Discord's REST ping; record what the loop asks for, in order."""

    ping_ms: int | Exception = 42
    calls: list[str] = field(default_factory=list[str])

    async def get(self, url: str) -> int:
        self.calls.append(f"get {url}")
        return 200

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


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PING)
def test_every_placeholder_is_replaced() -> None:
    """Requirement: The URL carries the REST ping."""
    template = "https://status.example.com/%ping%/push?ping=%ping%"

    assert build_url(template, 42) == "https://status.example.com/42/push?ping=42"
    assert build_url(template, -1) == "https://status.example.com/-1/push?ping=-1"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PING)
async def test_ping_in_the_url() -> None:
    """Requirement: The URL carries the REST ping."""
    fakes = Fakes(ping_ms=42)

    url = await fakes.pusher("https://status.example.com/%ping%/push?ping=%ping%").url()

    assert url == "https://status.example.com/42/push?ping=42"
    assert fakes.calls == ["ping"]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PING)
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


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PING)
async def test_no_placeholder() -> None:
    """Requirement: The URL carries the REST ping."""
    fakes = Fakes()
    plain = "https://status.example.com/api/push/xxxxxxxxxx?status=up"

    assert await fakes.pusher(plain).url() == plain
    assert fakes.calls == []  # v3 asked Discord at every push


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PING)
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
