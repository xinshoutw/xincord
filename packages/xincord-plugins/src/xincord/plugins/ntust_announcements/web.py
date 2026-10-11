"""The plugin's HTTP: NTUST's pages and the model's REST API, over one aiohttp session.

v3 fetched pages with Java's ``HttpClient``, which follows no redirect, and called Gemini through
the google-genai Java SDK, building a client per attempt that it never closed. One session serves
the plugin from READY until it unloads; the APIs' documented REST calls need no SDK (``api.py``).
"""

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import aiohttp

from xincord.plugins.ntust_tls import ntust_context

from .api import ApiError, answer_text, error_message

if TYPE_CHECKING:
    import ssl
    from collections.abc import AsyncGenerator

    from .api import Api

OK = 200
# v3's limits for pages: 30 seconds to connect and 30 for the request.
PAGE_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=30)
MAX_REDIRECTS = 10


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


def _json(text: str) -> object:
    """The JSON value of ``text``, or None when it is not JSON."""
    try:
        value: object = json.loads(text)
    except ValueError:
        return None
    return value


def _timeout(api: Api) -> aiohttp.ClientTimeout:
    """The limits of an attempt: ``request-timeout`` in all, ``connect-timeout`` to connect.

    v3's SDK set none; a long article can take the model a minute or more.
    """
    return aiohttp.ClientTimeout(total=api.request_timeout, connect=api.connect_timeout)


class Requests(Protocol):
    """What the plugin asks of the web: :class:`Web`, or a fake in tests."""

    async def page(self, url: str) -> Page:
        """GET a page."""
        ...

    async def generate(self, key: str, prompt: str) -> str:
        """One attempt with the model."""
        ...


@dataclass(frozen=True)
class Web:
    """The requests of a running plugin, over its session."""

    session: aiohttp.ClientSession
    api: Api  # the model's settings
    # NTUST's context for the pages (``xincord.plugins.ntust_tls``), not for the model's API.
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
        """One attempt: the model's text for ``prompt``, with ``key``, in the API's format.

        The key goes in a header, never in the URL; redirects are not followed.

        Raises:
            ApiError: The API answered with a status other than 200.
        """
        api = self.api
        async with self.session.post(
            api.url,
            json=api.body(prompt),
            headers=api.headers(key),
            timeout=_timeout(api),
            allow_redirects=False,
        ) as response:
            answer = _json(await response.text(errors="replace"))
            if response.status != OK:
                raise ApiError(response.status, error_message(answer))
            return answer_text(api.format, answer)


@asynccontextmanager
async def open_web(api: Api) -> AsyncGenerator[Web]:
    """A session for the plugin's requests with the model's settings, closed when the block ends."""
    async with aiohttp.ClientSession() as session:
        yield Web(session, api)
