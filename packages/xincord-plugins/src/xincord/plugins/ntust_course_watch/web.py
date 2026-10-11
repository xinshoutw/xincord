"""The plugin's HTTP: NTUST's course query, over one aiohttp session.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseApi.kt:51-92
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from .courses import Course

API = "https://querycourse.ntust.edu.tw/QueryCourse/api//courses"  # v3's URL, with its //
# v3's 5 seconds to connect; v3 set no limit for the answer, so a stalled one stopped its loop.
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=5)


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

    async def course(self, semester: str, code: str) -> Course | None:
        """Ask about ``code`` in ``semester``; None when the answer lists no such course."""
        raise NotImplementedError


@asynccontextmanager
async def open_api(url: str = API) -> AsyncGenerator[Api]:
    """A session for the plugin's requests, closed when the block ends."""
    async with aiohttp.ClientSession() as session:
        yield Api(session, url)
