"""The plugin's HTTP: NTUST's course query, over one aiohttp session."""

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import aiohttp

from xincord.plugins.ntust_tls import ntust_context

from .courses import AnswerError, read_course, request_text

if TYPE_CHECKING:
    import ssl
    from collections.abc import AsyncGenerator

    from .courses import Course

API = "https://querycourse.ntust.edu.tw/QueryCourse/api//courses"  # with its //
# 5 seconds to connect, 30 for the answer.
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=5)
HEADERS = {"content-type": "application/json; charset=utf-8"}
OK = 200


class Query(Protocol):
    """What the plugin asks of the course query: :class:`Api`, or a fake in tests."""

    async def course(self, semester: str, code: str) -> Course | None:
        """Ask about ``code`` in ``semester``."""
        ...


class QueryError(Exception):
    """The course query answered with a status other than 200."""

    def __init__(self, status: int) -> None:
        """Keep the status."""
        super().__init__(f"code {status}")
        self.status = status


@dataclass(frozen=True)
class Api:
    """The course query of a running plugin, over its session."""

    session: aiohttp.ClientSession
    url: str = API
    # NTUST's chains fail Python's strict X.509 checks (xincord.plugins.ntust_tls).
    tls: ssl.SSLContext = field(default_factory=ntust_context)
    timeout: aiohttp.ClientTimeout = TIMEOUT

    async def course(self, semester: str, code: str) -> Course | None:
        """Ask about ``code`` in ``semester``; None when the answer lists no such course.

        No redirect is followed.

        Raises:
            QueryError: The course query answered with a status other than 200.
            AnswerError: The answer is not JSON, or not what :func:`read_course` reads.
        """
        async with self.session.post(
            self.url,
            data=request_text(semester, code).encode(),
            headers=HEADERS,
            ssl=self.tls,
            timeout=self.timeout,
            allow_redirects=False,
        ) as response:
            if response.status != OK:
                raise QueryError(response.status)
            text = await response.text(errors="replace")
        try:
            answer: object = json.loads(text)
        except ValueError as error:
            msg = "the answer is not JSON"
            raise AnswerError(msg) from error
        return read_course(answer, code)


@asynccontextmanager
async def open_api(url: str = API) -> AsyncGenerator[Api]:
    """A session for the plugin's requests, closed when the block ends."""
    async with aiohttp.ClientSession() as session:
        yield Api(session, url)
