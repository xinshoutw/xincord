"""The plugin's HTTP: NTUST's pages and Gemini's REST API, over one aiohttp session.

v3 fetched pages with Java's ``HttpClient``, which follows no redirect, and called Gemini through
the google-genai Java SDK, building a client per attempt that it never closed. One session serves
the plugin from READY until it unloads; Gemini's documented REST call needs no SDK.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:19-102
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:111-150
"""

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, cast

import aiohttp

from xincord.plugins.ntust_tls import ntust_context

from .gemini import GeminiError
from .pages import trim

if TYPE_CHECKING:
    import ssl
    from collections.abc import AsyncGenerator

API = "https://generativelanguage.googleapis.com"  # Gemini's REST API
OK = 200
# v3's limits for pages: 30 seconds to connect and 30 for the request.
PAGE_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=30)
# v3's SDK set none for Gemini, which can take a minute or more for a long article.
GEMINI_TIMEOUT = aiohttp.ClientTimeout(total=300, connect=30)
MAX_REDIRECTS = 10
TEMPERATURE = 0.1  # v3's generation config


@dataclass(frozen=True)
class Page:
    """A page's text and its URL after redirects."""

    url: str
    text: str


class FetchError(Exception):
    """A page answered with a status other than 200."""

    def __init__(self, status: int) -> None:
        """Keep the status."""
        super().__init__(f"code {status}")
        self.status = status


def _field(value: object, name: str) -> object:
    """``value[name]`` when ``value`` is a JSON object, else None."""
    return cast("dict[str, object]", value).get(name) if isinstance(value, dict) else None


def _items(value: object) -> list[object]:
    """``value`` when it is a JSON array, else no items."""
    return cast("list[object]", value) if isinstance(value, list) else []


def _json(text: str) -> object:
    """The JSON value of ``text``, or None when it is not JSON."""
    try:
        value: object = json.loads(text)
    except ValueError:
        return None
    return value


def answer_text(answer: object) -> str:
    """The text of the first candidate's parts of Gemini's answer, joined and trimmed.

    v3's ``callOnce``; an answer without candidates (a blocked prompt), content or text parts gives
    an empty text, a failed attempt.
    """
    candidates = _items(_field(answer, "candidates"))
    if not candidates:
        return ""
    parts = _items(_field(_field(candidates[0], "content"), "parts"))
    texts = [text for part in parts if isinstance(text := _field(part, "text"), str)]
    return trim("".join(texts))


class Requests(Protocol):
    """What the plugin asks of the web: :class:`Web`, or a fake in tests."""

    async def page(self, url: str) -> Page:
        """GET a page."""
        ...

    async def generate(self, key: str, prompt: str) -> str:
        """One Gemini attempt."""
        ...


@dataclass(frozen=True)
class Web:
    """The requests of a running plugin, over its session."""

    session: aiohttp.ClientSession
    model: str
    api: str = API
    # NTUST's context for the pages (``xincord.plugins.ntust_tls``), not for Gemini.
    tls: ssl.SSLContext = field(default_factory=ntust_context)

    async def page(self, url: str) -> Page:
        """GET a page, following up to ten redirects (v3 followed none).

        Raises:
            FetchError: The page answered with a status other than 200.
        """
        async with self.session.get(
            url, ssl=self.tls, timeout=PAGE_TIMEOUT, max_redirects=MAX_REDIRECTS
        ) as response:
            if response.status != OK:
                raise FetchError(response.status)
            # The header's charset, else UTF-8, malformed bytes replaced, as Java's ofString().
            return Page(str(response.url), await response.text(errors="replace"))

    async def generate(self, key: str, prompt: str) -> str:
        """One Gemini attempt: the answer's text for ``prompt``, with ``key``.

        The key goes in the ``x-goog-api-key`` header, never in the URL; v3's temperature 0.1.

        Raises:
            GeminiError: Gemini answered with a status other than 200.
        """
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": TEMPERATURE},
        }
        async with self.session.post(
            f"{self.api}/v1beta/models/{self.model}:generateContent",
            json=body,
            headers={"x-goog-api-key": key},
            timeout=GEMINI_TIMEOUT,
            allow_redirects=False,
        ) as response:
            answer = _json(await response.text(errors="replace"))
            if response.status != OK:
                message = _field(_field(answer, "error"), "message")
                raise GeminiError(response.status, message if isinstance(message, str) else "")
            return answer_text(answer)


@asynccontextmanager
async def open_web(model: str, api: str = API) -> AsyncGenerator[Web]:
    """A session for the plugin's requests, closed when the block ends."""
    async with aiohttp.ClientSession() as session:
        yield Web(session, model, api)
