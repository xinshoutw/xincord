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
from xincord.plugins.redaction import redact

from .api import ApiError
from .strings import trim

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
# An attempt that did not reach the API: aiohttp's errors and OSError, timeouts included.
NETWORK_ERRORS = (aiohttp.ClientError, OSError)
BLANK = "blank"  # the kind of failure of an answer without text


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


@dataclass(frozen=True)
class Limits:
    """Each key's rate limit and the retries: ``config.yaml``'s settings, v3's by default."""

    rate_limit: int = PER_WINDOW  # attempts per key in a window
    rate_window: float = WINDOW  # the window's seconds
    max_attempts: int = MAX_ATTEMPTS  # per conversion
    retry_waits: tuple[float, ...] = BACKOFF  # after the first, second, ... failed attempt


def backoff(failed: int, waits: Sequence[float] = BACKOFF) -> float:
    """Seconds to wait after the ``failed``-th failed attempt: that wait, the last one repeating.

    v3's waits are 60, 300, 900, then 1800 seconds.
    """
    return waits[min(failed, len(waits)) - 1]


def counted(count: int, noun: str) -> str:
    """``count`` and ``noun``, plural unless the count is one: ``1 attempt``, ``3 attempts``."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


class KeyRing:
    """v3's client-side rate limit: each key's attempts in a sliding window.

    Keys are counted by their text, so a key listed twice has one budget, as v3's map by key. An
    attempt leaves the window when it is ``window`` seconds old; v3 kept it a moment longer and
    then slept a second. Finding a key and counting its attempt is one step, which v3's two locked
    steps were not.
    """

    def __init__(
        self, keys: Sequence[str], limit: int = PER_WINDOW, window: float = WINDOW
    ) -> None:
        """Start with no attempt counted, at the first key."""
        self.keys = tuple(keys)
        self.limit = limit  # attempts per key in the window (``rate-limit``)
        self.window = window  # the window's seconds (``rate-window``)
        self.next = 0  # where the next search starts: after the last key used (v3's apiKeyIndex)
        self.attempts: dict[str, deque[float]] = {}  # each key's attempts in the window

    def _attempts(self, key: str, now: float) -> deque[float]:
        """``key``'s attempts in the window that ends at ``now``."""
        attempts = self.attempts.setdefault(key, deque())
        while attempts and now - attempts[0] >= self.window:
            attempts.popleft()
        return attempts

    def take(self, now: float) -> int | None:
        """The position of the next key with room, its attempt counted; None if all are full."""
        for offset in range(len(self.keys)):
            index = (self.next + offset) % len(self.keys)
            attempts = self._attempts(self.keys[index], now)
            if len(attempts) < self.limit:
                attempts.append(now)
                self.next = (index + 1) % len(self.keys)
                return index
        return None

    def wait(self, now: float) -> float:
        """Seconds until a key has room again, when every key is full.

        That is when the oldest attempt among the keys leaves the window.
        """
        return min(self._attempts(key, now)[0] for key in self.keys) + self.window - now


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
    limits: Limits = Limits()
    # The endpoint and the request URL: error texts show their origins only.
    urls: tuple[str, ...] = ()
    # Failed attempts of every board: each kind once per episode (v3 logged every attempt).
    failures: Failures = field(default_factory=Failures)
    ring: KeyRing = field(init=False)

    def __post_init__(self) -> None:
        self.ring = KeyRing(self.keys, self.limits.rate_limit, self.limits.rate_window)

    def hide(self, text: str) -> str:
        """``text`` with no key and no private part of ``urls``: an error's text may quote them.

        Every URL in it is cut to its origin and the user info, path and query of ``urls`` are
        removed wherever they appear (a proxy's endpoint can hold a token), then every key.
        """
        text = redact(text, *self.urls)
        for key in sorted(set(self.keys), key=len, reverse=True):
            text = text.replace(key, HIDDEN)
        return text

    async def convert(self, html: str, link: Link) -> str | None:
        """The model's Markdown for the article, or None after ``max_attempts`` failed ones.

        v3's ``processHtmlContentWithRetry``: when every key is at its limit, it waits until one
        has room, which uses no attempt; after a failed attempt it waits the next of
        ``retry_waits`` (v3's 60, 300, 900, then 1800 seconds). Cancellation (an unload) ends the
        conversion at once.
        """
        limits = self.limits
        failed = 0
        while failed < limits.max_attempts:
            index = self.ring.take(self.clock())
            if index is None:
                wait = self.ring.wait(self.clock())
                logger.debug(
                    "NtustAnnouncements: every key is at its rate limit; waiting %.1f s", wait
                )
                await self.sleep(wait)
                continue
            text = await self._attempt(index, failed + 1, html, link)
            if text:
                return text
            failed += 1
            if failed < limits.max_attempts:
                await self.sleep(backoff(failed, limits.retry_waits))
        logger.error(
            "NtustAnnouncements: gave up converting %s after %s",
            link.url,
            counted(limits.max_attempts, "attempt"),
        )
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
            self._failed(BLANK, index, number, link, "the model gave no text")
            return ""
        if failed := self.failures.succeed():
            logger.info(
                "NtustAnnouncements: conversions work again after %s",
                counted(failed, "failed attempt"),
            )
        logger.debug(
            "NtustAnnouncements: converted %s on attempt %d with key %d",
            link.url,
            number,
            index + 1,
        )
        return text

    def _failed(self, kind: object, index: int, number: int, link: Link, detail: str) -> None:
        """Log a failed attempt: as a warning when its kind is new in the episode, else debug."""
        logger.log(
            logging.WARNING if self.failures.fail(kind) else logging.DEBUG,
            "NtustAnnouncements: conversion attempt %d of %d at %s failed with key %d: %s",
            number,
            self.limits.max_attempts,
            link.url,
            index + 1,
            self.hide(detail),
        )
