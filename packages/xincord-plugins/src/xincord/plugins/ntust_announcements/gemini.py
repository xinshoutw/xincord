"""Gemini's side of an article: v3's prompt, its keys' rate limit and its retries.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:29-218
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/util/UrlUtils.kt:37-46
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xincord.plugins.failures import Failures

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from datetime import datetime

    from .pages import Link

type Generate = Callable[[str, str], Awaitable[str]]  # one attempt: (key, prompt) to Markdown
type Sleep = Callable[[float], Awaitable[object]]

MAX_ATTEMPTS = 10  # v3's maxRetries


class GeminiError(Exception):
    """Gemini answered an attempt with a status other than 200."""

    def __init__(self, status: int, message: str) -> None:
        """Keep the status and Google's error message, if any."""
        super().__init__(f"code {status}: {message}" if message else f"code {status}")
        self.status = status


def fill_prompt(template: str, link: Link, html: str, now: datetime) -> str:
    """The prompt for ``link``'s article, its tokens replaced in one pass."""
    raise NotImplementedError


def backoff(failed: int) -> int:
    """Seconds to wait after the ``failed``-th failed attempt."""
    raise NotImplementedError


class KeyRing:
    """v3's client-side rate limit: each key's attempts in the last minute."""

    def __init__(self, keys: Sequence[str]) -> None:
        """Start with no attempt counted, at the first key."""
        self.keys = tuple(keys)

    def take(self, now: float) -> int | None:
        """The position of the next key with room, its attempt counted; None if all are full."""
        raise NotImplementedError

    def wait(self, now: float) -> float:
        """Seconds until a key has room again, when every key is full."""
        raise NotImplementedError


@dataclass
class Gemini:
    """Converts articles with Gemini, keys in turn, retrying failed attempts as v3 did."""

    keys: tuple[str, ...]
    prompt: str  # the config's template
    generate: Generate
    sleep: Sleep
    clock: Callable[[], float]  # monotonic seconds, for the rate limit
    now: Callable[[], datetime]  # the local time, for {{now}}
    failures: Failures = field(default_factory=Failures)

    async def convert(self, html: str, link: Link) -> str | None:
        """Gemini's Markdown for the article, or None after ``MAX_ATTEMPTS`` failed attempts."""
        raise NotImplementedError
