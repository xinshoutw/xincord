"""Fixtures for the UptimeHeartbeat tests: READY, Discord's REST API and a local status monitor."""

from typing import TYPE_CHECKING

import pytest
from discord.http import HTTPClient

from http_fakes import Monitor, running_monitor
from plugin_fakes import Ready

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from discord.http import Route


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loops wait for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@pytest.fixture(autouse=True)
def discord_requests(monkeypatch: pytest.MonkeyPatch) -> list[Route]:
    """Discord's REST requests, recorded instead of sent; each answers at once."""
    requests: list[Route] = []

    async def request(_http: HTTPClient, route: Route, **_kwargs: object) -> object:
        requests.append(route)
        return {}

    monkeypatch.setattr(HTTPClient, "request", request)
    return requests


@pytest.fixture
async def monitor() -> AsyncGenerator[Monitor]:
    """A status monitor on a free local port, answering 200 unless told otherwise."""
    async with running_monitor() as running:
        yield running
