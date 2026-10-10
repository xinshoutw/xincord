"""A local HTTP server for plugins that send HTTP requests, such as UptimeHeartbeat's pushes."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.test_utils import RawTestServer
from yarl import URL

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

WAIT = 5  # seconds before received() gives up


@dataclass
class Monitor:
    """A status monitor on 127.0.0.1: answers each path with its status, 200 by default.

    A 3xx answer redirects to ``/moved``. Requests to a path in ``silent`` get no answer until the
    client gives up or the monitor closes. ``requests`` records each request's method, path and
    query, in order.
    """

    statuses: dict[str, int] = field(default_factory=dict[str, int])
    silent: set[str] = field(default_factory=set[str])
    requests: list[tuple[str, URL]] = field(default_factory=list[tuple[str, URL]])
    root: str = ""  # scheme, host and port, set once the server runs
    _arrived: asyncio.Condition = field(default_factory=asyncio.Condition)
    _closing: asyncio.Event = field(default_factory=asyncio.Event)

    def url(self, path: str) -> str:
        """The URL of ``path`` (with its query, written as is) on this monitor."""
        return self.root + path

    async def received(self, count: int) -> None:
        """Wait until ``count`` requests have arrived.

        Raises:
            TimeoutError: They did not arrive within ``WAIT`` seconds.
        """
        async with asyncio.timeout(WAIT), self._arrived:
            await self._arrived.wait_for(lambda: len(self.requests) >= count)

    def close(self) -> None:
        """Answer the silent requests, so that the server can stop."""
        self._closing.set()

    async def handle(self, request: web.BaseRequest) -> web.StreamResponse:
        async with self._arrived:
            self.requests.append((request.method, request.rel_url))
            self._arrived.notify_all()
        if request.path in self.silent:
            # The server cancels this when the client disconnects. Answered when the monitor
            # closes, which would otherwise wait for the client to give up.
            await self._closing.wait()
        status = self.statuses.get(request.path, 200)
        redirect = 300 <= status < 400
        return web.Response(status=status, headers={"Location": "/moved"} if redirect else None)


@asynccontextmanager
async def running_monitor() -> AsyncGenerator[Monitor]:
    """Run a :class:`Monitor` on a free local port until the block ends."""
    monitor = Monitor()
    async with RawTestServer(monitor.handle) as server:
        monitor.root = str(server.make_url(""))
        try:
            yield monitor
        finally:
            monitor.close()
