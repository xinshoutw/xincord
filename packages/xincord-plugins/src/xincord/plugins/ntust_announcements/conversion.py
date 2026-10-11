"""An article's conversion by the model: v3's prompt, its keys' rate limit and its retries.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:29-218
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/util/UrlUtils.kt:37-46
"""

import logging
import re
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp

from xincord.plugins.failures import Failures

from .pages import trim

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from datetime import datetime

    from .pages import Link

type Generate = Callable[[str, str], Awaitable[str]]  # one attempt: (key, prompt) to Markdown
type Sleep = Callable[[float], Awaitable[object]]

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 10  # v3's maxRetries
BACKOFF = (60, 300, 900, 1800)  # v3's waits after the first, second, third and later failures
WINDOW = 60.0  # seconds in which a key takes at most PER_WINDOW attempts (v3's rateLimitWindowMs)
PER_WINDOW = 10  # v3's maxRequestsPerMinute
TOKEN = re.compile(r"\{\{(page_title|page_url|base_url|now|html)\}\}")
HOST = re.compile(r"https://([^/]+)")  # v3's extractDomainFromBaseUrl, its first match
DEFAULT_HOST = "ntust.edu.tw"
HIDDEN = "..."  # what stands for a key in a logged text
# An attempt that did not reach Gemini: aiohttp's errors and OSError, timeouts included.
NETWORK_ERRORS = (aiohttp.ClientError, OSError)
BLANK = "blank"  # the kind of failure of an answer without text


class ApiError(Exception):
    """The model's API answered an attempt with a status other than 200."""

    def __init__(self, status: int, message: str) -> None:
        """Keep the status and the API's error message, if any."""
        super().__init__(f"code {status}: {message}" if message else f"code {status}")
        self.status = status


def fill_prompt(template: str, link: Link, html: str, now: datetime) -> str:
    """The prompt for ``link``'s article, its tokens replaced in one pass.

    ``{{page_title}}`` is the entry's title, ``{{page_url}}`` its URL, ``{{base_url}}`` ``https://``
    and the URL's host (v3's first ``https://`` match, else ``ntust.edu.tw``), ``{{now}}`` the local
    time as ``yyyy-MM-dd HH:mm:ss`` and ``{{html}}`` the article's HTML. v3 chained Kotlin's
    ``replace`` calls, so tokens in the title or the article were replaced too; values are
    inserted as they are now.
    """
    host = match[1] if (match := HOST.search(link.url)) else DEFAULT_HOST
    values = {
        "page_title": link.title,
        "page_url": link.url,
        "base_url": f"https://{host}",
        "now": f"{now:%Y-%m-%d %H:%M:%S}",
        "html": html,
    }
    return TOKEN.sub(lambda token: values[token[1]], template)


def backoff(failed: int) -> int:
    """Seconds to wait after the ``failed``-th failed attempt: 60, 300, 900, then 1800."""
    return BACKOFF[min(failed, len(BACKOFF)) - 1]


class KeyRing:
    """v3's client-side rate limit: each key's attempts in the last minute.

    Keys are counted by their text, so a key listed twice has one budget, as v3's map by key. An
    attempt leaves the window when it is 60 seconds old; v3 kept it a moment longer and then slept
    a second. Finding a key and counting its attempt is one step, which v3's two locked steps were
    not.
    """

    def __init__(self, keys: Sequence[str]) -> None:
        """Start with no attempt counted, at the first key."""
        self.keys = tuple(keys)
        self.next = 0  # where the next search starts: after the last key used (v3's apiKeyIndex)
        self.attempts: dict[str, deque[float]] = {}  # each key's attempts in the window

    def _attempts(self, key: str, now: float) -> deque[float]:
        """``key``'s attempts in the window that ends at ``now``."""
        attempts = self.attempts.setdefault(key, deque())
        while attempts and now - attempts[0] >= WINDOW:
            attempts.popleft()
        return attempts

    def take(self, now: float) -> int | None:
        """The position of the next key with room, its attempt counted; None if all are full."""
        for offset in range(len(self.keys)):
            index = (self.next + offset) % len(self.keys)
            attempts = self._attempts(self.keys[index], now)
            if len(attempts) < PER_WINDOW:
                attempts.append(now)
                self.next = (index + 1) % len(self.keys)
                return index
        return None

    def wait(self, now: float) -> float:
        """Seconds until a key has room again, when every key is full.

        That is when the oldest attempt among the keys leaves the window.
        """
        return min(self._attempts(key, now)[0] for key in self.keys) + WINDOW - now


def describe(error: BaseException) -> str:
    """The error's message, or its type when it has none (aiohttp's timeouts may have none)."""
    return str(error) or type(error).__name__


def format_traceback(error: BaseException) -> str:
    """The error's traceback as ``logging`` prints it, without the last newline."""
    return "".join(traceback.format_exception(error)).rstrip("\n")


@dataclass
class Converter:
    """Converts articles with the model, keys in turn, retrying failed attempts as v3 did."""

    keys: tuple[str, ...]
    prompt: str  # the config's template
    generate: Generate
    sleep: Sleep
    clock: Callable[[], float]  # monotonic seconds, for the rate limit
    now: Callable[[], datetime]  # the local time, for {{now}}
    # Failed attempts of every board: each kind once per episode (v3 logged every attempt).
    failures: Failures = field(default_factory=Failures)
    ring: KeyRing = field(init=False)

    def __post_init__(self) -> None:
        self.ring = KeyRing(self.keys)

    def hide(self, text: str) -> str:
        """``text`` with every key replaced: the API's errors may quote one."""
        for key in sorted(set(self.keys), key=len, reverse=True):
            text = text.replace(key, HIDDEN)
        return text

    async def convert(self, html: str, link: Link) -> str | None:
        """The model's Markdown for the article, or None after ``MAX_ATTEMPTS`` failed attempts.

        v3's ``processHtmlContentWithRetry``: when every key is at its limit, it waits until one
        has room, which uses no attempt; after a failed attempt it waits 60, 300, 900, then 1800
        seconds. Cancellation (an unload) ends the conversion at once.
        """
        failed = 0
        while failed < MAX_ATTEMPTS:
            index = self.ring.take(self.clock())
            if index is None:
                wait = self.ring.wait(self.clock())
                logger.debug(
                    "NtustAnnouncements: every Gemini key is at its limit; waiting %.1f s", wait
                )
                await self.sleep(wait)
                continue
            text = await self._attempt(index, failed + 1, html, link)
            if text:
                return text
            failed += 1
            if failed < MAX_ATTEMPTS:
                await self.sleep(backoff(failed))
        logger.error("NtustAnnouncements: Gemini failed %d attempts at %s", MAX_ATTEMPTS, link.url)
        return None

    async def _attempt(self, index: int, number: int, html: str, link: Link) -> str:
        """One attempt with the key at ``index``: its text, or an empty one when it failed."""
        prompt = fill_prompt(self.prompt, link, html, self.now())
        try:
            text = trim(await self.generate(self.keys[index], prompt))
        except ApiError as error:
            self._failed(error.status, index, number, link, describe(error))
            return ""
        except NETWORK_ERRORS as error:
            self._failed(type(error), index, number, link, describe(error))
            return ""
        except Exception as error:  # noqa: BLE001 - any error fails the attempt, as in v3
            # Unexpected: its traceback, redacted, since logger.exception prints texts as they are.
            self._failed(type(error), index, number, link, f"\n{format_traceback(error)}")
            return ""
        if not text:
            self._failed(BLANK, index, number, link, "Gemini gave no text")
            return ""
        if failed := self.failures.succeed():
            logger.info("NtustAnnouncements: Gemini works again after %d failed attempts", failed)
        logger.debug(
            "NtustAnnouncements: Gemini converted %s on attempt %d with key %d",
            link.url,
            number,
            index + 1,
        )
        return text

    def _failed(self, kind: object, index: int, number: int, link: Link, detail: str) -> None:
        """Log a failed attempt: as a warning when its kind is new in the episode, else debug."""
        logger.log(
            logging.WARNING if self.failures.fail(kind) else logging.DEBUG,
            "NtustAnnouncements: Gemini attempt %d of %d at %s failed with key %d: %s",
            number,
            MAX_ATTEMPTS,
            link.url,
            index + 1,
            self.hide(detail),
        )
