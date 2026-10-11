"""The plugin's HTTP against a local server standing for NTUST and Gemini.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:19-102
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:111-150
"""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from aiohttp import web
from aiohttp.test_utils import RawTestServer

from plugin_fakes import FIXTURES
from xincord.plugins.ntust_announcements.gemini import GeminiError
from xincord.plugins.ntust_announcements.web import FetchError, Page, answer_text, open_web

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

MODEL = "gemini-2.5-flash"
BOARD = (FIXTURES / "plugins" / "ntust_announcements" / "student-dormitory.html").read_text(
    encoding="utf-8"
)
ANSWER = {
    "candidates": [
        {
            "content": {"parts": [{"text": "  # Title\n"}, {"text": "Body  \n"}], "role": "model"},
            "finishReason": "STOP",
        },
        {"content": {"parts": [{"text": "Another candidate"}]}},
    ]
}


@dataclass(frozen=True)
class Received:
    """A request that the server received."""

    method: str
    path: str
    query: str
    key: str | None  # the x-goog-api-key header
    body: str


@dataclass
class Server:
    """NTUST's pages and Gemini's API on 127.0.0.1; ``gemini`` is Gemini's status and body."""

    gemini: tuple[int, str] = (200, json.dumps(ANSWER))
    received: list[Received] = field(default_factory=list[Received])
    root: str = ""  # scheme, host and port, set once the server runs

    async def handle(self, request: web.BaseRequest) -> web.StreamResponse:
        self.received.append(
            Received(
                request.method,
                request.path,
                request.query_string,
                request.headers.get("x-goog-api-key"),
                await request.text(),
            )
        )
        match request.path:
            case "/board":
                return web.Response(text=BOARD, content_type="text/html", charset="utf-8")
            case "/moved":
                return web.Response(status=302, headers={"Location": "/board"})
            case "/latin":
                return web.Response(body=b"caf\xe9 \xff", content_type="text/html")
            case path if path.startswith("/v1beta/"):
                status, text = self.gemini
                return web.Response(status=status, text=text, content_type="application/json")
            case _:
                return web.Response(status=404)


@pytest.fixture
async def server() -> AsyncGenerator[Server]:
    """The local server, on a free port."""
    running = Server()
    async with RawTestServer(running.handle) as raw:
        running.root = str(raw.make_url(""))
        yield running


async def test_request(server: Server) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    async with open_web(MODEL, api=server.root) as web_:
        await web_.generate("key-one", "the prompt")

    [received] = server.received
    assert (received.method, received.path) == ("POST", f"/v1beta/models/{MODEL}:generateContent")
    assert received.query == ""  # the key is in the header only
    assert received.key == "key-one"
    assert json.loads(received.body) == {
        "contents": [{"parts": [{"text": "the prompt"}]}],
        "generationConfig": {"temperature": 0.1},
    }


async def test_answer(server: Server) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    async with open_web(MODEL, api=server.root) as web_:
        text = await web_.generate("key-one", "the prompt")

    assert text == "# Title\nBody"  # the first candidate's parts, joined and trimmed


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        pytest.param(
            (
                429,
                json.dumps(
                    {
                        "error": {
                            "code": 429,
                            "message": "Resource has been exhausted",
                            "status": "RESOURCE_EXHAUSTED",
                        }
                    }
                ),
            ),
            "code 429: Resource has been exhausted",
            id="error",
        ),
        pytest.param((500, "Internal Server Error"), "code 500", id="not JSON"),
        pytest.param((302, ""), "code 302", id="redirect"),
    ],
)
async def test_refused_answers(server: Server, answer: tuple[int, str], error: str) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    server.gemini = answer

    async with open_web(MODEL, api=server.root) as web_:
        with pytest.raises(GeminiError) as raised:
            await web_.generate("key-one", "the prompt")

    assert str(raised.value) == error
    assert raised.value.status == answer[0]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}), id="blocked"),
        pytest.param(
            json.dumps({"candidates": [{"content": {"parts": [{"text": " \n "}]}}]}), id="blank"
        ),
        pytest.param("not JSON", id="not JSON"),
    ],
)
async def test_answers_without_text(server: Server, body: str) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    server.gemini = (200, body)

    async with open_web(MODEL, api=server.root) as web_:
        assert await web_.generate("key-one", "the prompt") == ""


@pytest.mark.parametrize(
    ("answer", "text"),
    [
        pytest.param({}, "", id="empty"),
        pytest.param([], "", id="not an object"),
        pytest.param({"candidates": []}, "", id="no candidates"),
        pytest.param({"candidates": [{"finishReason": "SAFETY"}]}, "", id="no content"),
        pytest.param({"candidates": [{"content": {"parts": "x"}}]}, "", id="parts not a list"),
        pytest.param(
            {
                "candidates": [
                    {"content": {"parts": [{"functionCall": {"name": "f"}}, {"text": "a"}, 7]}}
                ]
            },
            "a",
            id="text parts only",
        ),
    ],
)
def test_answer_text(answer: object, text: str) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    assert answer_text(answer) == text


async def test_page(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(MODEL) as web_:
        page = await web_.page(f"{server.root}/board")

    assert page == Page(f"{server.root}/board", BOARD)
    assert server.received[0].method == "GET"


async def test_redirects(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(MODEL) as web_:
        page = await web_.page(f"{server.root}/moved")

    # v3 followed no redirect and read nothing; the links resolve against where it led.
    assert page == Page(f"{server.root}/board", BOARD)


async def test_page_status(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(MODEL) as web_:
        with pytest.raises(FetchError) as raised:
            await web_.page(f"{server.root}/missing")

    assert raised.value.status == 404
    assert str(raised.value) == "code 404"


async def test_page_encoding(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(MODEL) as web_:
        page = await web_.page(f"{server.root}/latin")

    # Without a charset, UTF-8 with replacement characters, as Java's BodyHandlers.ofString.
    assert page.text == "caf\N{REPLACEMENT CHARACTER} \N{REPLACEMENT CHARACTER}"
