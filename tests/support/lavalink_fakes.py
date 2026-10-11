"""A local Lavalink v4 node for the tests of MusicPlayer's lavalink.py adapter.

It speaks enough of Lavalink's protocol (https://lavalink.dev/api/): the WebSocket's ``ready``
and the events a test sends, track loads, player updates and player deletions, each checking the
password, and it records what the client sent. It listens on 127.0.0.1 only.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from aiohttp import web
from aiohttp.test_utils import TestServer

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

PASSWORD = "example-password"
SESSION = "session-1"
WAIT = 5  # seconds before a wait gives up
type Json = dict[str, Any]


def track(number: int, **info: object) -> Json:
    """A Lavalink track object: song ``number`` on YouTube, with ``info`` overriding its fields."""
    return {
        "encoded": f"QAAA{number}",
        "info": {
            "identifier": f"video{number}",
            "isSeekable": True,
            "author": f"Band {number}",
            "length": 214000,
            "isStream": False,
            "position": 0,
            "title": f"Song {number}",
            "uri": f"https://www.youtube.com/watch?v=video{number}",
            "artworkUrl": None,
            "isrc": None,
            "sourceName": "youtube",
            **info,
        },
        "pluginInfo": {},
        "userData": {},
    }


@dataclass
class FakeNode:
    """The node's state: its load answers, and what each client sent."""

    password: str = PASSWORD
    answers: dict[str, Json] = field(default_factory=dict[str, Json])  # loads by identifier
    handshakes: list[dict[str, str]] = field(default_factory=list[dict[str, str]])
    updates: list[tuple[str, Json]] = field(default_factory=list[tuple[str, Json]])
    deleted: list[str] = field(default_factory=list[str])
    loads: list[str] = field(default_factory=list[str])
    sockets: list[web.WebSocketResponse] = field(default_factory=list[web.WebSocketResponse])
    closed: int = 0  # the sockets that the clients closed
    hold: asyncio.Event | None = None  # when set, loads and deletions wait for it once recorded
    _changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    def app(self) -> web.Application:
        """The node's routes."""
        app = web.Application()
        app.router.add_get("/v4/websocket", self._websocket)
        app.router.add_get("/v4/loadtracks", self._load)
        app.router.add_patch("/v4/sessions/{session}/players/{guild}", self._update)
        app.router.add_delete("/v4/sessions/{session}/players/{guild}", self._delete)
        return app

    async def send(self, payload: Json) -> None:
        """Send ``payload`` to the client over the latest WebSocket, as the node's events."""
        await self.sockets[-1].send_json(payload)

    async def event(self, kind: str, guild: int, **fields: object) -> None:
        """Send an ``event`` op of ``kind`` about ``guild``'s player."""
        await self.send({"op": "event", "type": kind, "guildId": str(guild), **fields})

    async def until(self, condition: Callable[[], bool]) -> None:
        """Wait until ``condition`` holds after something the client sent.

        Raises:
            TimeoutError: It did not within ``WAIT`` seconds.
        """
        async with asyncio.timeout(WAIT), self._changed:
            await self._changed.wait_for(condition)

    async def _changes(self) -> None:
        async with self._changed:
            self._changed.notify_all()

    async def _held(self) -> None:
        if self.hold is not None:
            await self.hold.wait()

    def _authorized(self, request: web.Request) -> bool:
        return request.headers.get("Authorization") == self.password

    async def _websocket(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return web.Response(status=401)
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        self.handshakes.append(dict(request.headers))
        self.sockets.append(socket)
        await socket.send_json({"op": "ready", "resumed": False, "sessionId": SESSION})
        await self._changes()
        async for _ in socket:  # the client sends nothing that the tests need
            pass
        self.closed += 1
        await self._changes()
        return socket

    async def _load(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return web.Response(status=401)
        identifier = request.query["identifier"]
        self.loads.append(identifier)
        await self._changes()
        await self._held()
        return web.json_response(self.answers.get(identifier, {"loadType": "empty", "data": {}}))

    async def _update(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return web.Response(status=401)
        body: Json = await request.json()
        guild = request.match_info["guild"]
        self.updates.append((guild, body))
        await self._changes()
        return web.json_response(
            {
                "guildId": guild,
                "track": None,
                "volume": body.get("volume", 100),
                "paused": body.get("paused", False),
                "state": {"time": 0, "position": 0, "connected": True, "ping": 0},
                "voice": body.get("voice", {"token": "", "endpoint": "", "sessionId": ""}),
                "filters": {},
            }
        )

    async def _delete(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return web.Response(status=401)
        self.deleted.append(request.match_info["guild"])
        await self._changes()
        await self._held()
        return web.Response(status=204)


@asynccontextmanager
async def running_node(node: FakeNode) -> AsyncGenerator[int]:
    """Serve ``node`` on 127.0.0.1 and yield its port; close its sockets and the server after."""
    server = TestServer(node.app(), host="127.0.0.1")
    await server.start_server()
    try:
        yield cast("int", server.port)  # pyright: ignore[reportUnknownMemberType]
    finally:
        for socket in node.sockets:
            await socket.close()
        await server.close()
