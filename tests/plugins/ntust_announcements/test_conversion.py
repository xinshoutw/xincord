"""An article's conversion: the prompt, the keys' rate limit, the retries and their logs."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
import pytest

from xincord.plugins.ntust_announcements.api import ApiError
from xincord.plugins.ntust_announcements.conversion import (
    MAX_ATTEMPTS,
    Converter,
    KeyRing,
    Limits,
    backoff,
    fill_prompt,
)
from xincord.plugins.ntust_announcements.pages import Link

NOW = datetime(2026, 10, 11, 9, 5, 3)  # noqa: DTZ001 - the host's local time
URL = "https://student.ntust.edu.tw/p/406-1053-152183,r1436.php?Lang=zh-tw"
LINK = Link("STUDENT_DORMITORY", URL, "Dorm notice")
PROMPT = "{{page_title}}|{{page_url}}|{{base_url}}|{{now}}|{{html}}"
LOGGER = "xincord.plugins.ntust_announcements"
# An endpoint whose user info and path are secrets, as a proxy's can be.
ENDPOINT = "https://user:pass-secret@proxy.example.com/secret-token/v1"
REQUEST_URL = f"{ENDPOINT}/chat/completions"


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
    """The API's answers in turn (a text, or an error to raise); then ``Markdown``."""

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


def converter(
    answers: Answers,
    keys: tuple[str, ...] = ("key-one", "key-two"),
    limits: Limits | None = None,
    urls: tuple[str, ...] = (),
) -> Converter:
    """A converter with the fake time and answers, the default limits unless others are given."""
    time = answers.time
    return Converter(
        keys, PROMPT, answers, time.sleep, time.clock, lambda: NOW, limits or Limits(), urls
    )


def plugin_lines(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """The plugin's log lines at ``level``."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == level
    ]


def test_tokens() -> None:
    """Requirement: The prompt is filled in one pass."""
    prompt = fill_prompt(PROMPT, LINK, "<p>x</p>", NOW)

    assert prompt == (
        f"Dorm notice|{URL}|https://student.ntust.edu.tw|2026-10-11 09:05:03|<p>x</p>"
    )
    # Each occurrence; no other text changes.
    assert fill_prompt("{{html}} {{html}} {{other}}", LINK, "x", NOW) == "x x {{other}}"


def test_values_as_they_are() -> None:
    """Requirement: The prompt is filled in one pass."""
    link = Link("STUDENT_DORMITORY", URL, "About {{html}} and {{now}}")

    prompt = fill_prompt(PROMPT, link, "<p>{{page_url}}</p>", NOW)

    # Tokens in the title and in the article stay as written.
    assert prompt.startswith("About {{html}} and {{now}}|")
    assert prompt.endswith("|<p>{{page_url}}</p>")


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


async def test_keys_in_turn() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    answers = Answers(Time())
    conversions = converter(answers)

    texts = [await conversions.convert("<p>x</p>", LINK) for _ in range(3)]

    assert texts == ["Markdown"] * 3
    assert answers.keys() == ["key-one", "key-two", "key-one"]
    assert answers.calls[0][2] == fill_prompt(PROMPT, LINK, "<p>x</p>", NOW)


async def test_rate_limit() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    answers = Answers(time)
    conversions = converter(answers, keys=("key-one",))
    for _ in range(10):
        await conversions.convert("<p>x</p>", LINK)
        time.now += 1

    assert await conversions.convert("<p>x</p>", LINK) == "Markdown"

    # The eleventh attempt waited until the first was 60 seconds old; the wait used no attempt.
    assert time.sleeps == [50]
    assert [at for _, at, _ in answers.calls] == [*range(10), 60]


def test_window() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    ring = KeyRing(["key-one"])
    assert [ring.take(float(second)) for second in range(10)] == [0] * 10

    assert ring.take(59.5) is None  # ten attempts in the last 60 seconds
    assert ring.wait(59.5) == pytest.approx(0.5)
    assert ring.take(60.0) == 0  # the first attempt left the window


def test_a_key_listed_twice() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    ring = KeyRing(["same-key", "same-key", "other-key"])

    taken = [ring.take(0.0) for _ in range(21)]

    # One budget per key text: the two positions share ten attempts.
    assert taken == [0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 2, 2, 2, 2, 2, None]


async def test_retries() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    answers = Answers(time, [ApiError(500, "Internal error")] * MAX_ATTEMPTS)

    assert await converter(answers).convert("<p>x</p>", LINK) is None

    assert len(answers.calls) == 10
    assert time.sleeps == [60, 300, 900, 1800, 1800, 1800, 1800, 1800, 1800]


async def test_success_after_failures() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    # A blank answer and an unexpected error each fail an attempt.
    answers = Answers(time, [" \n ", RuntimeError("unexpected"), "Markdown"])

    assert await converter(answers).convert("<p>x</p>", LINK) == "Markdown"

    assert time.sleeps == [60, 300]
    assert answers.keys() == ["key-one", "key-two", "key-one"]


def test_backoff() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    assert [backoff(failed) for failed in range(1, 10)] == [60, 300, 900] + [1800] * 6


async def test_keys_hidden(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    keys = ("secret-key-one", "secret-key-two")
    answers = Answers(
        Time(),
        [
            ApiError(400, "API key not valid: secret-key-one"),
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


async def test_failure_episode(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    quota = ApiError(429, "Resource has been exhausted")
    answers = Answers(Time(), [quota, quota, quota])
    conversions = converter(answers)

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        for _ in range(3):  # the first converts after three failed attempts
            assert await conversions.convert("<p>x</p>", LINK) == "Markdown"

    warnings = plugin_lines(caplog, logging.WARNING)
    assert len(warnings) == 1  # the second and third 429 are debug lines
    assert "code 429" in warnings[0]
    infos = plugin_lines(caplog, logging.INFO)
    assert infos == ["NtustAnnouncements: conversions work again after 3 failed attempts"]


async def test_conversion_given_up(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    answers = Answers(Time(), [" "] * MAX_ATTEMPTS)

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await converter(answers).convert("<p>x</p>", LINK) is None

    assert plugin_lines(caplog, logging.ERROR) == [
        f"NtustAnnouncements: gave up converting {URL} after {MAX_ATTEMPTS} attempts"
    ]
    assert len(plugin_lines(caplog, logging.WARNING)) == 1  # gave no text


def test_configured_window() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    ring = KeyRing(["key-one"], limit=2, window=30.0)
    assert [ring.take(0.0), ring.take(1.0)] == [0, 0]

    assert ring.take(29.5) is None  # two attempts in the last 30 seconds
    assert ring.wait(29.5) == pytest.approx(0.5)
    assert ring.take(30.0) == 0  # the first attempt left the window


async def test_configured_rate_limit(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    answers = Answers(time)
    conversions = converter(
        answers, ("key-one",), Limits(rate_limit=2, rate_window=30), (ENDPOINT,)
    )
    for _ in range(2):
        await conversions.convert("<p>x</p>", LINK)
        time.now += 1

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await conversions.convert("<p>x</p>", LINK) == "Markdown"

    # The third attempt waited until the first was 30 seconds old; the wait used no attempt.
    assert time.sleeps == [28]
    assert [at for _, at, _ in answers.calls] == [0, 1, 30]
    assert plugin_lines(caplog, logging.DEBUG)[0] == (
        "NtustAnnouncements: every key is at its rate limit; waiting 28.0 s"
    )


@pytest.mark.parametrize(
    ("waits", "sleeps"),
    [
        pytest.param((5, 7, 9), [5, 7], id="a wait per failure"),
        pytest.param((5,), [5, 5], id="the last wait repeating"),
    ],
)
async def test_configured_retries(
    waits: tuple[float, ...], sleeps: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    time = Time()
    answers = Answers(time, [ApiError(500, "Internal error")] * 3)
    limits = Limits(max_attempts=3, retry_waits=waits)

    conversions = converter(answers, limits=limits, urls=(ENDPOINT,))

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await conversions.convert("<p>x</p>", LINK) is None

    assert len(answers.calls) == 3
    assert time.sleeps == sleeps
    assert plugin_lines(caplog, logging.WARNING) == [
        (
            f"NtustAnnouncements: conversion attempt 1 of 3 at {URL} failed with key 1: "
            "code 500: Internal error"
        )
    ]
    assert plugin_lines(caplog, logging.ERROR) == [
        f"NtustAnnouncements: gave up converting {URL} after 3 attempts"
    ]


def test_configured_backoff() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    assert [backoff(failed, (5, 7)) for failed in range(1, 5)] == [5, 7, 7, 7]


async def test_endpoint_hidden(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    answers = Answers(
        Time(),
        [
            # aiohttp's connect timeout names the whole URL.
            aiohttp.ConnectionTimeoutError(f"Connection timeout to host {REQUEST_URL}"),
            ApiError(404, "No route for POST /secret-token/v1/chat/completions"),
            RuntimeError(f"boom at {REQUEST_URL}"),
            "Markdown",
        ],
    )
    conversions = converter(answers, urls=(ENDPOINT, REQUEST_URL))

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await conversions.convert("<p>x</p>", LINK) == "Markdown"

    assert "secret" not in caplog.text
    warnings = plugin_lines(caplog, logging.WARNING)
    assert len(warnings) == 3
    assert warnings[0].endswith(
        "failed with key 1: Connection timeout to host https://proxy.example.com"
    )
    assert warnings[1].endswith("failed with key 2: code 404: No route for POST ...")
    assert warnings[2].endswith("RuntimeError: boom at https://proxy.example.com")


async def test_no_product_named(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    endpoint = "https://api.openai.com/v1"
    answers = Answers(Time(), [ApiError(500, "Internal error"), " "])
    conversions = converter(
        answers, limits=Limits(max_attempts=2), urls=(endpoint, f"{endpoint}/chat/completions")
    )

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await conversions.convert("<p>x</p>", LINK) is None  # two failed attempts
        for _ in range(3):  # three conversions that work end the episode
            assert await conversions.convert("<p>x</p>", LINK) == "Markdown"

    assert plugin_lines(caplog, logging.WARNING) == [
        (
            f"NtustAnnouncements: conversion attempt 1 of 2 at {URL} failed with key 1: "
            "code 500: Internal error"
        ),
        (
            f"NtustAnnouncements: conversion attempt 2 of 2 at {URL} failed with key 2: "
            "the model gave no text"
        ),
    ]
    assert plugin_lines(caplog, logging.ERROR) == [
        f"NtustAnnouncements: gave up converting {URL} after 2 attempts"
    ]
    assert plugin_lines(caplog, logging.INFO) == [
        "NtustAnnouncements: conversions work again after 2 failed attempts"
    ]
    assert plugin_lines(caplog, logging.DEBUG)[-1] == (
        f"NtustAnnouncements: converted {URL} on attempt 1 with key 1"
    )
    for record in caplog.records:
        assert "gemini" not in f"{record.name} {record.getMessage()}".lower()


async def test_counts_of_one(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    answers = Answers(Time(), [" "])
    conversions = converter(answers, limits=Limits(max_attempts=1), urls=(ENDPOINT,))

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert await conversions.convert("<p>x</p>", LINK) is None
        for _ in range(3):
            assert await conversions.convert("<p>x</p>", LINK) == "Markdown"

    assert plugin_lines(caplog, logging.ERROR) == [
        f"NtustAnnouncements: gave up converting {URL} after 1 attempt"
    ]
    assert plugin_lines(caplog, logging.INFO) == [
        "NtustAnnouncements: conversions work again after 1 failed attempt"
    ]


async def test_window_edge() -> None:
    """Requirement: API keys stay within the rate limit and failed attempts are retried."""
    # The key's only attempt leaves the window between two readings of the clock.
    readings = iter([0.0, 59.9999999, 60.0000001])
    time = Time()
    answers = Answers(time)
    conversions = Converter(
        ("key-one",),
        PROMPT,
        answers,
        time.sleep,
        lambda: next(readings, 60.0000002),
        lambda: NOW,
        Limits(rate_limit=1, rate_window=60),
    )

    assert await conversions.convert("<p>x</p>", LINK) == "Markdown"
    assert await conversions.convert("<p>x</p>", LINK) == "Markdown"

    assert time.sleeps == [pytest.approx(1e-7, abs=1e-9)]  # until the attempt left the window
    assert len(answers.calls) == 2


def warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The plugin's warnings."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == logging.WARNING
    ]


async def test_fenced_answer(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Answers that hold a refused text are retried."""
    answers = Answers(Time(), ["```markdown\n# Notice\n```", "# Notice"])
    convert = converter(answers)
    convert.reject = ("```",)

    assert await convert.convert("<p>x</p>", LINK) == "# Notice"
    assert answers.time.sleeps == [backoff(1)]
    [warning] = warnings(caplog)
    assert warning.endswith("failed with key 1: the answer holds ```")


async def test_nothing_refused() -> None:
    """Requirement: Answers that hold a refused text are retried."""
    answers = Answers(Time(), ["```\nx\n```"])
    convert = converter(answers)
    convert.reject = ()

    assert await convert.convert("<p>x</p>", LINK) == "```\nx\n```"
    assert answers.time.sleeps == []


def test_markdown_token() -> None:
    """Requirement: The prompt is filled in one pass."""
    template = "{{page_title}}|{{html}}|{{markdown}}"

    assert fill_prompt(template, LINK, "<p>x</p>", NOW, "# Draft") == "Dorm notice|<p>x</p>|# Draft"
    assert fill_prompt(template, LINK, "<p>x</p>", NOW) == "Dorm notice|<p>x</p>|"


async def test_review() -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    answers = Answers(Time(), ["```\nfenced\n```", "# Reviewed"])
    convert = converter(answers)
    convert.reject = ("```",)
    convert.review_prompt = "check {{markdown}} against {{html}}"

    assert await convert.review("<p>x</p>", LINK, "# Draft") == "# Reviewed"
    assert [prompt for _, _, prompt in answers.calls] == ["check # Draft against <p>x</p>"] * 2
    assert answers.time.sleeps == [backoff(1)]  # a review retries as a conversion does


async def test_review_gives_up(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    answers = Answers(Time(), ["", ""])
    convert = converter(answers, limits=Limits(max_attempts=2))
    convert.review_prompt = "check {{markdown}} against {{html}}"

    assert await convert.review("<p>x</p>", LINK, "# Draft") is None
    assert "review attempt 1 of 2" in warnings(caplog)[0]
    assert f"NtustAnnouncements: gave up reviewing {URL} after 2 attempts" in caplog.messages
