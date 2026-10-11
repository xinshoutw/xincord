"""The plugin's HTTP: NTUST's pages and Gemini's REST API, over one aiohttp session.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:19-102
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:111-150
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import aiohttp

API = "https://generativelanguage.googleapis.com"  # Gemini's REST API


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


def answer_text(answer: object) -> str:
    """The text of the first candidate's parts of Gemini's answer, joined and trimmed."""
    raise NotImplementedError


@dataclass(frozen=True)
class Web:
    """The requests of a running plugin, over its session."""

    session: aiohttp.ClientSession
    model: str
    api: str = API

    async def page(self, url: str) -> Page:
        """GET a page, following redirects."""
        raise NotImplementedError

    async def generate(self, key: str, prompt: str) -> str:
        """One Gemini attempt: the answer's text for ``prompt``, with ``key``."""
        raise NotImplementedError


@asynccontextmanager
async def open_web(model: str, api: str = API) -> AsyncGenerator[Web]:
    """A session for the plugin's requests, closed when the block ends."""
    del model, api
    raise NotImplementedError
    yield  # pragma: no cover
