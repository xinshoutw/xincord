"""Gemini's side of an article: v3's prompt, its keys' rate limit, its retries and their logs.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:35-218
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/util/UrlUtils.kt:37-46
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
import pytest

from xincord.plugins.ntust_announcements.gemini import (
    MAX_ATTEMPTS,
    Gemini,
    GeminiError,
    KeyRing,
    backoff,
    fill_prompt,
)
from xincord.plugins.ntust_announcements.pages import Link

NOW = datetime(2026, 10, 11, 9, 5, 3)  # noqa: DTZ001 - the host's local time, as v3's
URL = "https://student.ntust.edu.tw/p/406-1053-152183,r1436.php?Lang=zh-tw"
LINK = Link("STUDENT_DORMITORY", URL, "Dorm notice")
PROMPT = "{{page_title}}|{{page_url}}|{{base_url}}|{{now}}|{{html}}"
LOGGER = "xincord.plugins.ntust_announcements"


@dataclass
class Time:
    """A clock that the recorded sleeps move."""

    now: float = 0.0
    sleeps: list[float] = field(default_factory=list[float])

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


@dataclass
class Answers:
    """Gemini's answers in turn (a text, or an error to raise); then ``Markdown``."""

    time: Time
    results: list[str | Exception] = field(default_factory=list[str | Exception])
    calls: list[tuple[str, float, str]] = field(default_factory=list[tuple[str, float, str]])

    async def __call__(self, key: str, prompt: str) -> str:
        self.calls.append((key, self.time.now, prompt))
        result = self.results.pop(0) if self.results else "Markdown"
        if isinstance(result, Exception):
            raise result
        return result

    def keys(self) -> list[str]:
        return [key for key, _, _ in self.calls]


def converter(answers: Answers, keys: tuple[str, ...] = ("key-one", "key-two")) -> Gemini:
    """A Gemini with the fake time and answers."""
    time = answers.time
    return Gemini(keys, PROMPT, answers, time.sleep, time.clock, lambda: NOW)


def plugin_lines(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """The plugin's log lines at ``level``."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == level
    ]


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The prompt is filled in one pass"
)
def test_tokens() -> None:
    """Requirement: The prompt is filled in one pass."""
    prompt = fill_prompt(PROMPT, LINK, "<p>x</p>", NOW)

    assert prompt == (
        f"Dorm notice|{URL}|https://student.ntust.edu.tw|2026-10-11 09:05:03|<p>x</p>"
    )
    # Each occurrence, as Kotlin's replace; no other text changes.
    assert fill_prompt("{{html}} {{html}} {{other}}", LINK, "x", NOW) == "x x {{other}}"


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The prompt is filled in one pass"
)
def test_values_as_they_are() -> None:
    """Requirement: The prompt is filled in one pass."""
    link = Link("STUDENT_DORMITORY", URL, "About {{html}} and {{now}}")

    prompt = fill_prompt(PROMPT, link, "<p>{{page_url}}</p>", NOW)

    # v3's chained replace calls expanded the tokens in the title and in the article.
    assert prompt.startswith("About {{html}} and {{now}}|")
    assert prompt.endswith("|<p>{{page_url}}</p>")


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The prompt is filled in one pass"
)
@pytest.mark.parametrize(
    ("url", "base"),
    [
        pytest.param(URL, "https://student.ntust.edu.tw", id="article"),
        pytest.param(
            "https://lc.ntust.edu.tw:8443/p/1.php", "https://lc.ntust.edu.tw:8443", id="port"
        ),
        pytest.param("http://www.example.com/a", "https://ntust.edu.tw", id="no https"),
        pytest.param(
            "https://www.google.com/url?q=https://student.ntust.edu.tw/p/1.php",
            "https://www.google.com",
            id="first match",
        ),
    ],
)
def test_base_url(url: str, base: str) -> None:
    """Requirement: The prompt is filled in one pass."""
    assert fill_prompt("{{base_url}}", Link("B", url, "t"), "", NOW) == base


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Gemini keys stay within the rate limit and failed attempts are retried",
)
async def test_keys_in_turn() -> None:
    """Requirement: Gemini keys stay within the rate limit and failed attempts are retried."""
    answers = Answers(Time())
    gemini = converter(answers)

    texts = [await gemini.convert("<p>x</p>", LINK) for _ in range(3)]

    assert texts == ["Markdown"] * 3
    assert answers.keys() == ["key-one", "key-two", "key-one"]
    assert answers.calls[0][2] == fill_prompt(PROMPT, LINK, "<p>x</p>", NOW)


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Gemini keys stay within the rate limit and failed attempts are retried",
)
async def test_rate_limit() -> None:
    """Requirement: Gemini keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    answers = Answers(time)
    gemini = converter(answers, keys=("key-one",))
    for _ in range(10):
        await gemini.convert("<p>x</p>", LINK)
        time.now += 1

    assert await gemini.convert("<p>x</p>", LINK) == "Markdown"

    # The eleventh attempt waited until the first was 60 seconds old; the wait used no attempt.
    assert time.sleeps == [50]
    assert [at for _, at, _ in answers.calls] == [*range(10), 60]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Gemini keys stay within the rate limit and failed attempts are retried",
)
def test_window() -> None:
    """Requirement: Gemini keys stay within the rate limit and failed attempts are retried."""
    ring = KeyRing(["key-one"])
    assert [ring.take(float(second)) for second in range(10)] == [0] * 10

    assert ring.take(59.5) is None  # ten attempts in the last 60 seconds
    assert ring.wait(59.5) == pytest.approx(0.5)
    assert ring.take(60.0) == 0  # the first attempt left the window


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Gemini keys stay within the rate limit and failed attempts are retried",
)
def test_a_key_listed_twice() -> None:
    """Requirement: Gemini keys stay within the rate limit and failed attempts are retried."""
    ring = KeyRing(["same-key", "same-key", "other-key"])

    taken = [ring.take(0.0) for _ in range(21)]

    # One budget per key text, as v3's map by key: the two positions share ten attempts.
    assert taken == [0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 2, 2, 2, 2, 2, None]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Gemini keys stay within the rate limit and failed attempts are retried",
)
async def test_retries() -> None:
    """Requirement: Gemini keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    answers = Answers(time, [GeminiError(500, "Internal error")] * MAX_ATTEMPTS)

    assert await converter(answers).convert("<p>x</p>", LINK) is None

    assert len(answers.calls) == 10
    assert time.sleeps == [60, 300, 900, 1800, 1800, 1800, 1800, 1800, 1800]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Gemini keys stay within the rate limit and failed attempts are retried",
)
async def test_success_after_failures() -> None:
    """Requirement: Gemini keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    # A blank answer and an unexpected error each fail an attempt, as in v3.
    answers = Answers(time, [" \n ", RuntimeError("unexpected"), "Markdown"])

    assert await converter(answers).convert("<p>x</p>", LINK) == "Markdown"

    assert time.sleeps == [60, 300]
    assert answers.keys() == ["key-one", "key-two", "key-one"]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Gemini keys stay within the rate limit and failed attempts are retried",
)
def test_backoff() -> None:
    """Requirement: Gemini keys stay within the rate limit and failed attempts are retried."""
    assert [backoff(failed) for failed in range(1, 10)] == [60, 300, 900] + [1800] * 6


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Problems are logged without flooding or showing the keys",
)
async def test_keys_hidden(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    keys = ("secret-key-one", "secret-key-two")
    answers = Answers(
        Time(),
        [
            GeminiError(400, "API key not valid: secret-key-one"),
            aiohttp.ClientConnectionError("cannot connect with secret-key-two"),
            RuntimeError("boom with secret-key-one"),
            "Markdown",
        ],
    )

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await converter(answers, keys).convert("<p>x</p>", LINK) == "Markdown"

    assert "secret-key" not in caplog.text
    warnings = plugin_lines(caplog, logging.WARNING)
    assert len(warnings) == 3
    assert "failed with key 1: code 400: API key not valid: ..." in warnings[0]
    assert "failed with key 2: cannot connect with ..." in warnings[1]
    assert "failed with key 1:" in warnings[2]
    assert "RuntimeError: boom with ..." in warnings[2]  # an unexpected error's traceback
    assert URL in warnings[0]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Problems are logged without flooding or showing the keys",
)
async def test_gemini_failure_episode(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    quota = GeminiError(429, "Resource has been exhausted")
    answers = Answers(Time(), [quota, quota, quota])
    gemini = converter(answers)

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        for _ in range(3):  # the first converts after three failed attempts
            assert await gemini.convert("<p>x</p>", LINK) == "Markdown"

    warnings = plugin_lines(caplog, logging.WARNING)
    assert len(warnings) == 1  # the second and third 429 are debug lines
    assert "code 429" in warnings[0]
    infos = plugin_lines(caplog, logging.INFO)
    assert infos == ["NtustAnnouncements: Gemini works again after 3 failed attempts"]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Problems are logged without flooding or showing the keys",
)
async def test_conversion_given_up(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    answers = Answers(Time(), [" "] * MAX_ATTEMPTS)

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await converter(answers).convert("<p>x</p>", LINK) is None

    assert plugin_lines(caplog, logging.ERROR) == [
        f"NtustAnnouncements: Gemini failed {MAX_ATTEMPTS} attempts at {URL}"
    ]
    assert len(plugin_lines(caplog, logging.WARNING)) == 1  # gave no text
