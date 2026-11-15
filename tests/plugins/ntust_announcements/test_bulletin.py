"""The plugin's HTTP: bulletin's API, served by a local server."""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from aiohttp import web
from aiohttp.test_utils import RawTestServer

from xincord.plugins.ntust_announcements.bulletin import AnswerError, FetchError, open_bulletin

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

XFAIL = pytest.mark.xfail(strict=True, reason="read-bulletin-feed")
ITEM = {
    "id": 1697,
    "site": 1053,
    "unit": "student",
    "url": "https://student.ntust.edu.tw/p/406-1053-153594.php",
    "link_item": False,
    "title": "Dormitory registration",
    "publisher": None,
    "day": "2026-11-11",
    "boards": ["1053-1436"],
    "tags": {"topic": ["housing"], "audience": [], "nature": [], "source": []},
    "rendition": {"title": "Registration", "summary": "Register.", "deadline": "2026-11-25"},
}
EVENTS = {
    "events": [
        {
            "id": 2836,
            "kind": "published",
            "notify": True,
            "late": False,
            "at": "2026-11-16T01:00:00+00:00",
            "announcement": ITEM,
        },
        {
            "id": 2837,
            "kind": "archived",  # a kind added later
            "notify": False,
            "late": False,
            "at": "2026-11-16T01:01:00+00:00",
            "announcement": ITEM | {"rendition": None},
        },
    ],
    "last": 2837,
}
ANNOUNCEMENT = ITEM | {
    "body_html": "<p>text</p>",
    "rendition": {"title": "Registration", "summary": None, "deadline": None, "markdown": "**m**"},
    "attachments": [
        {"name": "form.pdf", "url": "https://student.ntust.edu.tw/a.pdf", "size": 8, "file": None}
    ],
    "revisions": [],
    "cross_posts": [],
    "cross_post_of": None,
}


@dataclass
class Server:
    """bulletin's API under ``/api/v1``: each path's status and body, others a 404."""

    answers: dict[str, tuple[int, str]] = field(default_factory=dict[str, tuple[int, str]])
    received: list[str] = field(default_factory=list[str])
    root: str = ""  # the API's URL, once the server runs

    async def handle(self, request: web.BaseRequest) -> web.StreamResponse:
        self.received.append(request.path_qs)
        status, text = self.answers.get(request.path, (404, '{"detail": "no announcement"}'))
        return web.Response(status=status, text=text, content_type="application/json")


@pytest.fixture
async def server() -> AsyncGenerator[Server]:
    """The local server, on a free port."""
    running = Server()
    async with RawTestServer(running.handle) as raw:
        running.root = str(raw.make_url("/api/v1"))
        yield running


@XFAIL
async def test_events(server: Server) -> None:
    """Requirement: The first read starts at the feed's end."""
    server.answers["/api/v1/events"] = (200, json.dumps(EVENTS))

    async with open_bulletin(server.root) as api:
        events = await api.events(2835)

    assert server.received == ["/api/v1/events?after=2835&limit=500"]
    first, later = events.events
    assert (first.id, first.kind, first.notify) == (2836, "published", True)
    assert first.announcement.boards == ("1053-1436",)
    assert (later.kind, later.announcement.rendition, events.last) == ("archived", None, 2837)


@XFAIL
async def test_an_announcement(server: Server) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    server.answers["/api/v1/announcements/1697"] = (200, json.dumps(ANNOUNCEMENT))

    async with open_bulletin(server.root) as api:
        found = await api.announcement(1697)

    assert found is not None
    assert found.rendition is not None
    assert found.rendition.markdown == "**m**"
    assert [(a.name, a.url) for a in found.attachments] == [
        ("form.pdf", "https://student.ntust.edu.tw/a.pdf")
    ]


@XFAIL
async def test_an_unknown_announcement(server: Server) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    async with open_bulletin(server.root) as api:
        assert await api.announcement(999999) is None


@XFAIL
@pytest.mark.parametrize("path", ["/api/v1/events", "/api/v1/announcements/1697"])
async def test_a_failing_status(server: Server, path: str) -> None:
    """Requirement: Problems are logged without flooding."""
    server.answers[path] = (503, "Service Unavailable")

    async with open_bulletin(server.root) as api:
        with pytest.raises(FetchError) as raised:
            await (api.events(0) if path.endswith("events") else api.announcement(1697))

    assert raised.value.status == 503


@XFAIL
@pytest.mark.parametrize("body", ["<html>maintenance</html>", '{"events": []}', "[]"])
async def test_an_unexpected_answer(server: Server, body: str) -> None:
    """Requirement: Problems are logged without flooding."""
    server.answers["/api/v1/events"] = (200, body)
    server.answers["/api/v1/announcements/1"] = (200, body)

    async with open_bulletin(server.root) as api:
        with pytest.raises(AnswerError):
            await api.events(0)
        with pytest.raises(AnswerError):
            await api.announcement(1)
