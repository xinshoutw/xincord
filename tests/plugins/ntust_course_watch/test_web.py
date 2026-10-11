"""The course query over HTTP, against a local server standing for NTUST."""

import json
import ssl
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import RawTestServer

from plugin_fakes import FIXTURES, golden
from xincord.plugins.ntust_course_watch.courses import AnswerError, Course
from xincord.plugins.ntust_course_watch.web import API, TIMEOUT, QueryError, open_api

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

GOLDEN = golden("ntust_course_watch")
ANSWER = (FIXTURES / "plugins" / "ntust_course_watch" / "answer.json").read_text("utf-8")
PATH = "/QueryCourse/api//courses"  # v3's path, with its //


@dataclass(frozen=True)
class Received:
    """A request that the server received."""

    method: str
    path: str
    query: str
    content_type: str | None
    body: str


@dataclass
class Server:
    """NTUST's course query on 127.0.0.1: ``answer`` is its status and body."""

    answer: tuple[int, str] = (200, ANSWER)
    received: list[Received] = field(default_factory=list[Received])
    root: str = ""  # scheme, host and port, set once the server runs

    async def handle(self, request: web.BaseRequest) -> web.StreamResponse:
        self.received.append(
            Received(
                request.method,
                request.raw_path.split("?")[0],
                request.query_string,
                request.headers.get("content-type"),
                await request.text(),
            )
        )
        if request.raw_path == "/moved":
            return web.Response(status=200, text="[]", content_type="application/json")
        status, text = self.answer
        headers = {"Location": "/moved"} if 300 <= status < 400 else None
        return web.Response(
            status=status, text=text, content_type="application/json", headers=headers
        )

    @property
    def url(self) -> str:
        """The course query's URL on this server."""
        return f"{self.root}{PATH}"


@pytest.fixture
async def server() -> AsyncGenerator[Server]:
    """The local server, on a free port."""
    running = Server()
    async with RawTestServer(running.handle) as raw:
        running.root = str(raw.make_url("")).rstrip("/")
        yield running


async def test_request(server: Server) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    async with open_api(server.url) as api:
        await api.course("1151", "CE162A001")

    [received] = server.received
    assert (received.method, received.path, received.query) == ("POST", PATH, "")
    assert received.content_type == "application/json; charset=utf-8"
    assert received.body == GOLDEN["request"]


async def test_answer(server: Server) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    expected = GOLDEN["courses"]["CE162A001"]

    async with open_api(server.url) as api:
        course = await api.course("1151", "CE162A001")

    assert course == Course("CE162A001", expected["name"], expected["chosen"], expected["limit"])


async def test_course_missing(server: Server) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    async with open_api(server.url) as api:
        assert await api.course("1151", "CE162A099") is None


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param((500, json.dumps({"Message": "error"})), id="server error"),
        pytest.param((404, ""), id="not found"),
        pytest.param((302, ""), id="redirect"),
    ],
)
async def test_refused_statuses(server: Server, answer: tuple[int, str]) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    server.answer = answer

    async with open_api(server.url) as api:
        with pytest.raises(QueryError) as raised:
            await api.course("1151", "CE162A001")

    assert raised.value.status == answer[0]
    assert str(raised.value) == f"code {answer[0]}"
    assert [received.path for received in server.received] == [PATH]  # no redirect followed


@pytest.mark.parametrize(
    ("text", "message"),
    [
        pytest.param("not JSON", "not JSON", id="not JSON"),
        pytest.param(json.dumps({"Message": "error"}), "not a list", id="not a list"),
    ],
)
async def test_refused_answers(server: Server, text: str, message: str) -> None:
    """Requirement: Course seats come from NTUST's course query."""
    server.answer = (200, text)

    async with open_api(server.url) as api:
        with pytest.raises(AnswerError, match=message):
            await api.course("1151", "CE162A001")


async def test_defaults() -> None:
    """Requirement: Course seats come from NTUST's course query."""
    assert API == "https://querycourse.ntust.edu.tw/QueryCourse/api//courses"  # v3's URL
    # v3's 5 seconds to connect; v3 waited for the answer without a limit.
    assert (TIMEOUT.connect, TIMEOUT.total) == (5, 30)
    async with open_api() as api:
        assert api.url == API
        assert api.timeout == TIMEOUT
        assert isinstance(api.session, aiohttp.ClientSession)


async def test_ntust_certificates() -> None:
    """Requirement: Course seats come from NTUST's course query."""
    # querycourse.ntust.edu.tw's chain lacks a Subject Key Identifier, which Python 3.13's strict
    # X.509 checks refuse (2026-10-11): the context shared with NtustAnnouncements verifies the
    # certificate and the host name without them, with TWCA's intermediate.
    async with open_api() as api:
        tls = api.tls
        assert not tls.verify_flags & ssl.VERIFY_X509_STRICT
        assert tls.verify_mode == ssl.CERT_REQUIRED
        assert tls.check_hostname
        subjects = [str(ca["subject"]) for ca in tls.get_ca_certs()]
    assert any("'TWCA Secure SSL Certification Authority'" in subject for subject in subjects)
