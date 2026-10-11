"""The plugin's HTTP against a local server standing for NTUST and the model's API."""

import hashlib
import json
import ssl
from dataclasses import dataclass, field
from importlib.resources import files
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import RawTestServer

from plugin_fakes import FIXTURES
from xincord.plugins.ntust_announcements.api import (
    Api,
    ApiError,
    ApiFormat,
    answer_text,
    error_message,
)
from xincord.plugins.ntust_announcements.web import FetchError, Page, open_web
from xincord.plugins.ntust_tls import ntust_context

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
OPENAI_ANSWER = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "  # Title\nBody  \n"},
            "finish_reason": "stop",
        },
        {"index": 1, "message": {"role": "assistant", "content": "Another choice"}},
    ],
}
OPENAI_ERROR = {
    "error": {
        "message": "Incorrect API key provided",
        "type": "invalid_request_error",
        "code": "invalid_api_key",
    }
}


@dataclass(frozen=True)
class Received:
    """A request that the server received."""

    method: str
    path: str
    query: str
    key: str | None  # the x-goog-api-key header
    authorization: str | None  # the Authorization header
    body: str


@dataclass
class Server:
    """NTUST's pages (GET) and the model's API (POST) on 127.0.0.1.

    ``api`` is the API's status and body for every POST.
    """

    api: tuple[int, str] = (200, json.dumps(ANSWER))
    received: list[Received] = field(default_factory=list[Received])
    root: str = ""  # scheme, host and port, set once the server runs

    async def handle(self, request: web.BaseRequest) -> web.StreamResponse:
        self.received.append(
            Received(
                request.method,
                request.path,
                request.query_string,
                request.headers.get("x-goog-api-key"),
                request.headers.get("Authorization"),
                await request.text(),
            )
        )
        if request.method == "POST":
            status, text = self.api
            return web.Response(status=status, text=text, content_type="application/json")
        match request.path:
            case "/board":
                return web.Response(text=BOARD, content_type="text/html", charset="utf-8")
            case "/moved":
                return web.Response(status=302, headers={"Location": "/board"})
            case "/latin":
                return web.Response(body=b"caf\xe9 \xff", content_type="text/html")
            case _:
                return web.Response(status=404)


@pytest.fixture
async def server() -> AsyncGenerator[Server]:
    """The local server, on a free port."""
    running = Server()
    async with RawTestServer(running.handle) as raw:
        running.root = str(raw.make_url(""))
        yield running


def gemini(server: Server, **settings: Any) -> Api:  # noqa: ANN401 - Api's own types
    """The settings of an API under the local server's ``/v1beta``, as Gemini's."""
    return Api(endpoint=f"{server.root}/v1beta", **settings)


def openai(server: Server, **settings: Any) -> Api:  # noqa: ANN401 - Api's own types
    """The settings of an OpenAI-compatible API at the local server, as Gemini's own."""
    return Api(format=ApiFormat.OPENAI, endpoint=f"{server.root}/v1beta/openai", **settings)


async def test_request(server: Server) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    async with open_web(gemini(server)) as web_:
        await web_.generate("key-one", "the prompt")

    [received] = server.received
    assert (received.method, received.path) == ("POST", f"/v1beta/models/{MODEL}:generateContent")
    assert received.query == ""  # the key is in the header only
    assert received.key == "key-one"
    assert received.authorization is None
    assert json.loads(received.body) == {
        "contents": [{"parts": [{"text": "the prompt"}]}],
        "generationConfig": {"temperature": 0.1},
    }


async def test_request_settings(server: Server) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    api = Api(
        endpoint=f"{server.root}/proxy/v1beta",
        model="gemini-2.5-pro",
        temperature=0.7,
        max_output_tokens=2048,
    )

    async with open_web(api) as web_:
        await web_.generate("key-one", "the prompt")

    [received] = server.received
    assert received.path == "/proxy/v1beta/models/gemini-2.5-pro:generateContent"
    assert received.key == "key-one"
    assert json.loads(received.body) == {
        "contents": [{"parts": [{"text": "the prompt"}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }


async def test_request_without_settings(server: Server) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    async with open_web(gemini(server, temperature=None, max_output_tokens=None)) as web_:
        await web_.generate("key-one", "the prompt")

    # Both left to the API's defaults: no generationConfig at all.
    assert json.loads(server.received[0].body) == {
        "contents": [{"parts": [{"text": "the prompt"}]}]
    }


async def test_timeouts(server: Server, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    timeouts: list[object] = []
    post = aiohttp.ClientSession.post

    def recording(session: aiohttp.ClientSession, url: str, **options: Any) -> Any:  # noqa: ANN401
        timeouts.append(options.get("timeout"))
        return post(session, url, **options)

    monkeypatch.setattr(aiohttp.ClientSession, "post", recording)

    async with open_web(gemini(server)) as web_:
        await web_.generate("key-one", "the prompt")  # v3's: 300 seconds, 30 to connect
    async with open_web(gemini(server, request_timeout=120, connect_timeout=10)) as web_:
        await web_.generate("key-one", "the prompt")

    assert timeouts == [
        aiohttp.ClientTimeout(total=300, connect=30),
        aiohttp.ClientTimeout(total=120, connect=10),
    ]


async def test_answer(server: Server) -> None:
    """Requirement: Gemini turns an article into Markdown."""
    async with open_web(gemini(server)) as web_:
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
    server.api = answer

    async with open_web(gemini(server)) as web_:
        with pytest.raises(ApiError) as raised:
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
    server.api = (200, body)

    async with open_web(gemini(server)) as web_:
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
    assert answer_text(ApiFormat.GEMINI, answer) == text


async def test_openai_request(server: Server) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    server.api = (200, json.dumps(OPENAI_ANSWER))

    async with open_web(openai(server)) as web_:
        await web_.generate("key-one", "the prompt")

    [received] = server.received
    assert (received.method, received.path) == ("POST", "/v1beta/openai/chat/completions")
    assert received.query == ""  # the key is in the header only
    assert received.authorization == "Bearer key-one"
    assert received.key is None
    assert json.loads(received.body) == {
        "model": MODEL,
        "messages": [{"role": "user", "content": "the prompt"}],
        "temperature": 0.1,
    }


async def test_openai_settings(server: Server) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    server.api = (200, json.dumps(OPENAI_ANSWER))
    api = Api(
        format=ApiFormat.OPENAI,
        endpoint=f"{server.root}/api/v1",
        model="openai/gpt-4o-mini",
        temperature=None,
        max_output_tokens=512,
    )

    async with open_web(api) as web_:
        await web_.generate("key-one", "the prompt")

    [received] = server.received
    assert received.path == "/api/v1/chat/completions"
    assert json.loads(received.body) == {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "the prompt"}],
        "max_tokens": 512,
    }


async def test_openai_answer(server: Server) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    server.api = (200, json.dumps(OPENAI_ANSWER))

    async with open_web(openai(server)) as web_:
        text = await web_.generate("key-one", "the prompt")

    assert text == "# Title\nBody"  # the first choice's content, trimmed


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        pytest.param(
            (401, json.dumps(OPENAI_ERROR)), "code 401: Incorrect API key provided", id="error"
        ),
        pytest.param((500, "Internal Server Error"), "code 500", id="not JSON"),
        pytest.param((302, ""), "code 302", id="redirect"),
    ],
)
async def test_openai_refused_answers(server: Server, answer: tuple[int, str], error: str) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    server.api = answer

    async with open_web(openai(server)) as web_:
        with pytest.raises(ApiError) as raised:
            await web_.generate("key-one", "the prompt")

    assert str(raised.value) == error
    assert raised.value.status == answer[0]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(json.dumps({"choices": []}), id="no choices"),
        pytest.param(
            json.dumps({"choices": [{"message": {"role": "assistant", "content": None}}]}),
            id="null content",
        ),
        pytest.param(json.dumps({"choices": [{"message": {"content": " \n "}}]}), id="blank"),
        pytest.param("not JSON", id="not JSON"),
    ],
)
async def test_openai_answers_without_text(server: Server, body: str) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    server.api = (200, body)

    async with open_web(openai(server)) as web_:
        assert await web_.generate("key-one", "the prompt") == ""


@pytest.mark.parametrize(
    ("answer", "text"),
    [
        pytest.param({}, "", id="empty"),
        pytest.param([], "", id="not an object"),
        pytest.param({"choices": "x"}, "", id="choices not a list"),
        pytest.param({"choices": [dict[str, object]()]}, "", id="no message"),
        pytest.param({"choices": [{"message": "x"}]}, "", id="message not an object"),
        pytest.param({"choices": [{"message": {"content": ["a"]}}]}, "", id="content parts"),
        pytest.param({"choices": [{"message": {"refusal": "No."}}]}, "", id="refusal"),
        pytest.param({"choices": [{"message": {"content": " a "}}]}, "a", id="text"),
    ],
)
def test_openai_answer_text(answer: object, text: str) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    assert answer_text(ApiFormat.OPENAI, answer) == text


# Gemini's OpenAI-compatible endpoint answers an error as a list of one error object.
GEMINI_OPENAI_ERROR = [
    {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
        }
    }
]


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        pytest.param(
            GEMINI_OPENAI_ERROR, "API key not valid. Please pass a valid API key.", id="error list"
        ),
        pytest.param({"error": "model not loaded"}, "model not loaded", id="error text"),
        pytest.param([], "", id="empty list"),
        pytest.param([{"error": 7}], "", id="list without a message"),
    ],
)
def test_error_messages(answer: object, message: str) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    assert error_message(answer) == message


async def test_openai_error_list(server: Server) -> None:
    """Requirement: An OpenAI-compatible API turns an article into Markdown."""
    server.api = (400, json.dumps(GEMINI_OPENAI_ERROR))

    async with open_web(openai(server)) as web_:
        with pytest.raises(ApiError) as raised:
            await web_.generate("key-one", "the prompt")

    assert str(raised.value) == "code 400: API key not valid. Please pass a valid API key."


async def test_page(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(Api()) as web_:
        page = await web_.page(f"{server.root}/board")

    assert page == Page(f"{server.root}/board", BOARD)
    assert server.received[0].method == "GET"


async def test_redirects(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(Api()) as web_:
        page = await web_.page(f"{server.root}/moved")

    # v3 followed no redirect and read nothing; the links resolve against where it led.
    assert page == Page(f"{server.root}/board", BOARD)


async def test_page_status(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(Api()) as web_:
        with pytest.raises(FetchError) as raised:
            await web_.page(f"{server.root}/missing")

    assert raised.value.status == 404
    assert str(raised.value) == "code 404"


async def test_page_encoding(server: Server) -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(Api()) as web_:
        page = await web_.page(f"{server.root}/latin")

    # Without a charset, UTF-8 with replacement characters, as Java's BodyHandlers.ofString.
    assert page.text == "caf\N{REPLACEMENT CHARACTER} \N{REPLACEMENT CHARACTER}"


def test_page_certificates() -> None:
    """Requirement: Board pages list their announcements."""
    context = ntust_context()

    # Python 3.13 made the strict X.509 checks a default, and NTUST's certificate chain lacks a
    # Subject Key Identifier, which they refuse (2026-10-11); Java's HttpClient took it.
    assert ssl.create_default_context().verify_flags & ssl.VERIFY_X509_STRICT
    assert not context.verify_flags & ssl.VERIFY_X509_STRICT
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


async def test_pages_use_the_context() -> None:
    """Requirement: Board pages list their announcements."""
    async with open_web(Api()) as web_:
        assert not web_.tls.verify_flags & ssl.VERIFY_X509_STRICT
        assert web_.tls.check_hostname


def test_missing_intermediate() -> None:
    """Requirement: Board pages list their announcements."""
    # www.academic.ntust.edu.tw sends its own certificate and the root, not TWCA's intermediate
    # (2026-10-11), so OpenSSL cannot build its chain; the page context holds the intermediate.
    subjects = [str(ca["subject"]) for ca in ntust_context().get_ca_certs()]

    assert any("'TWCA Secure SSL Certification Authority'" in subject for subject in subjects)


def test_bundled_intermediate() -> None:
    """Requirement: Board pages list their announcements."""
    text = files("xincord.plugins.ntust_tls").joinpath("twca-secure-ssl-ca.pem")
    pem = text.read_text("ascii")
    block = pem[pem.index("-----BEGIN CERTIFICATE-----") :]

    # The certificate that student.ntust.edu.tw sends after its own, as of 2026-10-11.
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(block)).hexdigest() == (
        "1a2c75fd096e0499e9ff6ac74e526f61eaae3edfc8c2ea4436fee0c24d8b7d0e"
    )
