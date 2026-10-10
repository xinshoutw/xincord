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

from xincord.plugins.uptime_heartbeat.config import Listener
from xincord.plugins.uptime_heartbeat.pusher import Pusher, build_url, rest_ping

if TYPE_CHECKING:
    from discord.http import Route

TOKEN = "xxxxxxxxxx"  # the push token: in the URL's path, never in a log line
URL = f"https://status.example.com/api/push/{TOKEN}?status=up&msg=OK&ping=%ping%"
PUSHED = URL.replace("%ping%", "42")
ENDPOINT = "https://status.example.com"  # the URL's origin, all that the logs show of it


class Stop(Exception):  # noqa: N818 - it ends the loop, it reports no error
    """Raised by the fake sleep to end a loop that would push forever."""


@dataclass
class Fakes:
    """Stand in for the monitor, Discord's REST ping and the clock; record the loop's calls.

    The monitor answers the pushes with ``answers`` in turn, repeating the last one, and Discord
    the pings with ``pings``; an exception is raised instead. Each push takes ``push_seconds`` on
    the fake clock ``now``, and the sleep after the ``stop_after``-th push raises :class:`Stop`.
    """

    answers: tuple[int | Exception, ...] = (200,)
    pings: tuple[int | Exception, ...] = (42,)
    push_seconds: float = 0
    stop_after: int = 1
    calls: list[str] = field(default_factory=list[str])
    starts: list[float] = field(default_factory=list[float])  # the clock when each push began
    now: float = 0
    pushes: int = 0
    measured: int = 0  # pings asked for

    async def get(self, url: str) -> int:
        self.calls.append(f"get {url}")
        self.starts.append(self.now)
        self.now += self.push_seconds
        answer = self.answers[min(self.pushes, len(self.answers) - 1)]
        self.pushes += 1
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def ping(self) -> int:
        self.calls.append("ping")
        answer = self.pings[min(self.measured, len(self.pings) - 1)]
        self.measured += 1
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def sleep(self, seconds: float) -> None:
        self.calls.append(f"sleep {seconds}")
        self.now += seconds
        if self.pushes >= self.stop_after:
            raise Stop

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
    fakes = Fakes(pings=(42,))

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
    fakes = Fakes(pings=(error,))

    with caplog.at_level(logging.WARNING):
        url = await fakes.pusher().url()

    assert url == URL.replace("%ping%", "-1")
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage().startswith(
        "UptimeHeartbeat listener 1 could not measure the REST ping, so %ping% is -1: "
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


def records_above(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno > level]


@pytest.mark.parametrize("status", [200, 204, 299])
async def test_success(status: int, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    with caplog.at_level(logging.DEBUG, "xincord.plugins.uptime_heartbeat"):
        await Fakes(answers=(status,)).pusher().push()

    assert records_above(caplog, logging.DEBUG) == []
    assert caplog.messages == [f"UptimeHeartbeat listener 1 pushed to {ENDPOINT} (code {status})"]


async def test_not_found(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    await Fakes(answers=(404,)).pusher().push()

    # Uptime Kuma's answer for an unknown or paused push token; the loop goes on (v3 stopped it).
    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.WARNING
    assert record.getMessage() == (
        f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed with code 404 "
        "(the status monitor refused the push)"
    )


async def test_monitor_offline(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    await Fakes(answers=(521,)).pusher().push()

    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.WARNING
    assert record.getMessage() == (
        f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed with code 521 "
        "(the status monitor is offline)"
    )


@pytest.mark.parametrize("status", [500, 302, 401])
async def test_other_status(status: int, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    await Fakes(answers=(status,)).pusher().push()

    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.ERROR
    assert record.getMessage() == (
        f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed with code {status}"
    )


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
    await Fakes(answers=(error,)).pusher().push()

    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.ERROR
    # No traceback for a network error.
    assert (
        record.getMessage() == f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed: {text}"
    )
    assert record.exc_info is None


async def test_unexpected_error(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The status code decides what follows."""
    await Fakes(answers=(ValueError("unexpected"),)).pusher().push()

    [record] = records_above(caplog, logging.INFO)
    assert record.levelno == logging.ERROR
    # The traceback, for a failure nobody expected, is part of the message.
    message = record.getMessage()
    assert message.startswith(
        f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed\n"
        "Traceback (most recent call last):\n"
    )
    assert message.endswith("\nValueError: unexpected")


async def test_pushes_that_fail_or_work(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs show only the URL's origin."""
    timeout = aiohttp.ConnectionTimeoutError(f"Connection timeout to host {PUSHED}")
    unexpected = ValueError(f"unexpected answer from {PUSHED}")
    answers = (200, 500, 302, timeout, unexpected, 200)
    fakes = Fakes(answers=answers, stop_after=len(answers))

    with caplog.at_level(logging.DEBUG, "xincord.plugins.uptime_heartbeat"), pytest.raises(Stop):
        await fakes.pusher().run()

    start, *pushes = caplog.messages
    assert start == "UptimeHeartbeat listener 1 started (every 60 s)"
    assert len(pushes) >= len(answers)
    assert all(ENDPOINT in message for message in pushes)
    assert TOKEN not in caplog.text
    assert "/api/push" not in caplog.text


async def test_port_and_user_info(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs show only the URL's origin."""
    url = f"http://user:secret@127.0.0.1:3001/api/push/{TOKEN}"

    await Fakes(answers=(500,)).pusher(url).push()

    [record] = records_above(caplog, logging.INFO)
    assert record.getMessage() == (
        "UptimeHeartbeat listener 1: pushing to http://127.0.0.1:3001 failed with code 500"
    )
    assert "secret" not in caplog.text
    assert TOKEN not in caplog.text


async def test_url_in_an_errors_text(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs show only the URL's origin."""
    # aiohttp 3.14.4's connect timeout names the whole URL.
    timeout = aiohttp.ConnectionTimeoutError(f"Connection timeout to host {PUSHED}")

    await Fakes(answers=(timeout,)).pusher().push()

    [record] = records_above(caplog, logging.INFO)
    assert record.getMessage() == (
        f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed: "
        f"Connection timeout to host {ENDPOINT}"
    )


async def test_url_in_a_traceback(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs show only the URL's origin."""
    await Fakes(answers=(ValueError(f"unexpected answer from {PUSHED}"),)).pusher().push()

    [record] = records_above(caplog, logging.INFO)
    message = record.getMessage()
    assert "Traceback (most recent call last):" in message
    assert message.endswith(f"\nValueError: unexpected answer from {ENDPOINT}")
    assert TOKEN not in caplog.text


async def test_first_push_at_once(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Each listener pushes at once, then after a fixed delay."""
    fakes = Fakes(stop_after=2)

    with caplog.at_level(logging.INFO), pytest.raises(Stop):
        await fakes.pusher(interval=60).run()

    push = ["ping", f"get {PUSHED}"]
    assert fakes.calls == [*push, "sleep 60", *push, "sleep 60"]
    assert caplog.messages == ["UptimeHeartbeat listener 1 started (every 60 s)"]


async def test_fixed_delay() -> None:
    """Requirement: Each listener pushes at once, then after a fixed delay."""
    fakes = Fakes(push_seconds=30, stop_after=3)

    with pytest.raises(Stop):
        await fakes.pusher(interval=60).run()

    # The delay follows each attempt, as v3's: not a fixed rate (0, 60, 120).
    assert fakes.starts == [0, 90, 180]


async def test_every_attempt_is_followed_by_the_delay() -> None:
    """Requirement: Each listener pushes at once, then after a fixed delay."""
    failures = (500, aiohttp.ClientConnectionError("refused"), 521, ValueError("unexpected"))
    fakes = Fakes(answers=(*failures, 200), stop_after=5)

    with pytest.raises(Stop):
        await fakes.pusher(interval=5).run()

    assert fakes.pushes == 5
    assert [call for call in fakes.calls if call.startswith("sleep")] == ["sleep 5"] * 5


async def test_pushing_goes_on_after_a_404() -> None:
    """Requirement: Each listener pushes at once, then after a fixed delay."""
    fakes = Fakes(answers=(200, 404, 404, 200), stop_after=4)

    with pytest.raises(Stop):  # v3 ended the loop after a 404, until a reload or restart
        await fakes.pusher().run()

    assert fakes.pushes == 4
    assert [call for call in fakes.calls if call.startswith("sleep")] == ["sleep 60"] * 4


def logged(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    """The plugin's lines after its start line, as (level, message) pairs."""
    return [
        (record.levelno, record.getMessage())
        for record in caplog.records
        if record.name.startswith("xincord.plugins.uptime_heartbeat")
        and not record.getMessage().startswith("UptimeHeartbeat listener 1 started")
    ]


def above_debug(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(level, message) for level, message in logged(caplog) if level > logging.DEBUG]


async def run_logged(fakes: Fakes, caplog: pytest.LogCaptureFixture) -> None:
    """Run listener 1 until the fake sleep stops it, with the plugin's debug lines captured."""
    with caplog.at_level(logging.DEBUG, "xincord.plugins.uptime_heartbeat"), pytest.raises(Stop):
        await fakes.pusher().run()


async def test_repeated_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A failure is logged when it starts, changes or ends."""
    await run_logged(Fakes(answers=(500,), stop_after=3), caplog)

    failure = f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed with code 500"
    assert logged(caplog) == [
        (logging.ERROR, failure),
        (logging.DEBUG, failure),  # v3 logged an error at every push
        (logging.DEBUG, failure),
    ]


async def test_another_kind_of_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A failure is logged when it starts, changes or ends."""
    refused = aiohttp.ClientConnectionError("Cannot connect to host status.example.com:443")
    answers = (500, 500, refused, 404, 404)

    await run_logged(Fakes(answers=answers, stop_after=len(answers)), caplog)

    failed = f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed"
    assert above_debug(caplog) == [
        (logging.ERROR, f"{failed} with code 500"),
        (logging.ERROR, f"{failed}: Cannot connect to host status.example.com:443"),
        (logging.WARNING, f"{failed} with code 404 (the status monitor refused the push)"),
    ]


@pytest.mark.parametrize(("failures", "count"), [(1, "1 failed push"), (2, "2 failed pushes")])
async def test_pushing_works_again(
    failures: int, count: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: A failure is logged when it starts, changes or ends."""
    answers = (*(500,) * failures, 200, 500)

    await run_logged(Fakes(answers=answers, stop_after=len(answers)), caplog)

    failure = f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} failed with code 500"
    works = f"UptimeHeartbeat listener 1: pushing to {ENDPOINT} works again after {count}"
    assert above_debug(caplog) == [
        (logging.ERROR, failure),
        (logging.INFO, works),
        (logging.ERROR, failure),  # a new failure once pushing worked
    ]


async def test_ping_fails_repeatedly(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A failure is logged when it starts, changes or ends."""
    fakes = Fakes(pings=(TimeoutError(), TimeoutError(), TimeoutError(), 42), stop_after=4)

    await run_logged(fakes, caplog)

    failure = "UptimeHeartbeat listener 1 could not measure the REST ping, so %ping% is -1: "
    assert above_debug(caplog) == [
        (logging.WARNING, f"{failure}TimeoutError"),
        (logging.INFO, "UptimeHeartbeat listener 1 measures the REST ping again"),
    ]
    assert logged(caplog).count((logging.DEBUG, f"{failure}TimeoutError")) == 2
    pushed = [call for call in fakes.calls if call.startswith("get ")]
    assert pushed == [f"get {URL.replace('%ping%', '-1')}"] * 3 + [f"get {PUSHED}"]
