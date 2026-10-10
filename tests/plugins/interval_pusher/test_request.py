"""Each push is one GET request, here to a local status monitor.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:20-22
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:67-99
"""

from typing import TYPE_CHECKING

import aiohttp
import pytest
from yarl import URL

from xincord.plugins.interval_pusher.pusher import get_status, open_session

if TYPE_CHECKING:
    from http_fakes import Monitor

XFAIL = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Each push is one GET request"
)


@XFAIL
async def test_status_code(monitor: Monitor) -> None:
    """Requirement: Each push is one GET request."""
    monitor.statuses["/api/push/token"] = 204

    async with open_session() as session:
        status = await get_status(session, monitor.url("/api/push/token?status=up&ping=42"))

    assert status == 204
    assert monitor.requests == [("GET", URL("/api/push/token?status=up&ping=42"))]


@XFAIL
async def test_redirect(monitor: Monitor) -> None:
    """Requirement: Each push is one GET request."""
    monitor.statuses["/api/push/token"] = 302  # to /moved

    async with open_session() as session:
        status = await get_status(session, monitor.url("/api/push/token"))

    assert status == 302  # v3's Java client did not follow redirects either
    assert monitor.requests == [("GET", URL("/api/push/token"))]


@XFAIL
async def test_limits() -> None:
    """Requirement: Each push is one GET request."""
    async with open_session() as session:
        assert session.timeout == aiohttp.ClientTimeout(total=30, connect=10)
