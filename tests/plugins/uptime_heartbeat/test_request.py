"""Each push is one GET request, here to a local status monitor or a server answering garbage.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:20-22
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:67-99
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp
import pytest
from yarl import URL

from xincord.plugins.uptime_heartbeat.config import Listener
from xincord.plugins.uptime_heartbeat.pusher import Pusher, get_status, open_session

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from http_fakes import Monitor

TOKEN = "xxxxxxxxxx"  # the push token: in the URL's path, never in a log line
ORIGIN_ONLY = "Logs show only the URL's origin"


async def test_status_code(monitor: Monitor) -> None:
    """Requirement: Each push is one GET request."""
    monitor.statuses["/api/push/token"] = 204

    async with open_session() as session:
        status = await get_status(session, monitor.url("/api/push/token?status=up&ping=42"))

    assert status == 204
    assert monitor.requests == [("GET", URL("/api/push/token?status=up&ping=42"))]


async def test_redirect(monitor: Monitor) -> None:
    """Requirement: Each push is one GET request."""
    monitor.statuses["/api/push/token"] = 302  # to /moved

    async with open_session() as session:
        status = await get_status(session, monitor.url("/api/push/token"))

    assert status == 302  # v3's Java client did not follow redirects either
    assert monitor.requests == [("GET", URL("/api/push/token"))]


async def test_limits() -> None:
    """Requirement: Each push is one GET request."""
    async with open_session() as session:
        assert session.timeout == aiohttp.ClientTimeout(total=30, connect=10)


type Answer = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


async def push_once(answer: Answer) -> str:
    """Push once, as listener 1, to a local server that answers with ``answer``; return its root."""

    async def no_ping() -> int:
        raise AssertionError  # the URL has no %ping%

    async def no_sleep(_seconds: float) -> None:
        raise AssertionError  # one push, no loop

    server = await asyncio.start_server(answer, "127.0.0.1", 0)
    root = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    listener = Listener(url=f"{root}/api/push/{TOKEN}?status=up", interval=60)
    async with server, open_session() as session:
        pusher = Pusher(
            1, listener, get=lambda url: get_status(session, url), ping=no_ping, sleep=no_sleep
        )
        await pusher.push()
    return root


async def test_malformed_answer(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs show only the URL's origin."""

    async def answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"not an HTTP answer\r\n\r\n")
        await writer.drain()
        writer.close()

    root = await push_once(answer)

    # aiohttp's own error for the answer names the whole URL: the log names its origin only.
    [record] = [record for record in caplog.records if record.levelno > logging.INFO]
    message = record.getMessage()
    assert message.startswith(f"UptimeHeartbeat listener 1: pushing to {root} failed: 400, ")
    assert message.endswith(f"url='{root}'")
    assert TOKEN not in caplog.text


@pytest.mark.xfail(strict=True, reason=ORIGIN_ONLY)
async def test_answer_that_quotes_the_request(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Logs show only the URL's origin."""

    async def answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_line = await reader.readline()
        await reader.readuntil(b"\r\n\r\n")
        writer.write(request_line + b"\r\n")  # the request line as the status line
        await writer.drain()
        writer.close()

    root = await push_once(answer)

    # aiohttp's parser quotes the bad status line, which holds the path and the query.
    [record] = [record for record in caplog.records if record.levelno > logging.INFO]
    assert record.getMessage().startswith(f"UptimeHeartbeat listener 1: pushing to {root} failed: ")
    assert "GET ... HTTP/1.1" in caplog.text
    assert TOKEN not in caplog.text
    assert "/api/push" not in caplog.text
