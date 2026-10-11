"""The plugin's ``config.yaml``: v3's keys, and the boards, channels and model settings that v3
hard-coded.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/config/ConfigSerializer.kt:6-26
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:33-36
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:220-238
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:31-115
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementTypes.kt:24-45
"""

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from xincord.core.config import Model

from .api import (
    CONNECT_TIMEOUT,
    GEMINI_ENDPOINT,
    GEMINI_MODEL,
    REQUEST_TIMEOUT,
    TEMPERATURE,
    Api,
    ApiFormat,
)
from .conversion import BACKOFF, MAX_ATTEMPTS, PER_WINDOW, WINDOW, Limits

if TYPE_CHECKING:
    from urllib.parse import SplitResult

JAVA_LONG_MAX = 2**63 - 1  # v3's fetch-interval was a Long
MIN_INTERVAL = 60  # v3's minimum, which it checked only while enabled
# v3's placeholder key, which its bundled file held twice and which it refused while enabled.
EXAMPLE_KEY = "sk-thisisatestkey1234567890abcdef1234567890"
# The tokens that v3's validateConfiguration required; {{page_title}} was optional.
TOKENS = ("{{page_url}}", "{{base_url}}", "{{now}}", "{{html}}")
SCHEMES = frozenset({"http", "https"})
# Bounds of the model settings: wider than any API's documented values, they refuse units typed
# wrongly (milliseconds for seconds, a size for a count).
MODEL = re.compile(r"\S{1,256}")
GEMINI_MODEL_NAME = re.compile(r"[A-Za-z0-9._-]+")  # it goes into the URL's path
MAX_OUTPUT_TOKENS = 2**20
MAX_TIMEOUT = 3600.0  # an hour
MAX_RATE_LIMIT = 10_000
DAY = 86_400.0
MOST_ATTEMPTS = 100
MOST_WAITS = 100
ENDPOINT = "must be an http or https URL with a host, without user info, a query or a fragment"
# pydantic's errors show no input: the core logs them with their traceback, and keys are secrets.
HIDDEN = ConfigDict(hide_input_in_errors=True)


class Layout(StrEnum):
    """How a board's first page lists its entries: v3's three parsers."""

    STUDENT_AFFAIRS = "student-affairs"  # a table, the title link in each row's first cell
    ACADEMIC_AFFAIRS = "academic-affairs"  # a table, the title link in each row's second cell
    LANGUAGE_CENTER = "language-center"  # rows of divisions, one title link each


def _key(key: str) -> str:
    """Accept an API key; the messages never quote it, nor name an API."""
    if not key.strip():
        msg = "must not be blank"
        raise ValueError(msg)
    if key == EXAMPLE_KEY:
        msg = "replace the example key with your API key"
        raise ValueError(msg)
    return key


def _some_keys(keys: tuple[str, ...]) -> tuple[str, ...]:
    """Refuse an empty list once its keys are valid: pydantic's ``min_length`` counts valid ones."""
    if not keys:
        msg = "list at least one key"
        raise ValueError(msg)
    return keys


def _http_url(url: str) -> SplitResult | None:
    """``url``'s parts if it is an http or https URL with a host, a valid port and no spaces."""
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises ValueError unless the port is a number from 0 to 65535
    except ValueError:
        return None
    if (
        parts.scheme not in SCHEMES
        or not parts.hostname
        or any(character.isspace() for character in url)
    ):
        return None
    return parts


def _page_url(url: str) -> str:
    """Accept an http or https URL with a host and no spaces, such as a board's first page."""
    if _http_url(url) is None:
        msg = "must be an http or https URL with a host and no spaces"
        raise ValueError(msg)
    return url


def _endpoint(url: str) -> str:
    """Accept the model's API: an http or https URL without user info, a query or a fragment.

    Each format appends its path, and keys belong in ``api-keys``; a final ``/`` is dropped. The
    message never quotes the URL, whose path can hold a proxy's token.
    """
    parts = _http_url(url)
    if parts is None or "@" in parts.netloc or "?" in url or "#" in url:
        raise ValueError(ENDPOINT)
    return url.rstrip("/")


def _some_waits(waits: tuple[float, ...]) -> tuple[float, ...]:
    """Refuse an empty list of waits: after the first failed attempt, a conversion waits."""
    if not waits:
        msg = "list at least one wait"
        raise ValueError(msg)
    return waits


def _prompt(prompt: str) -> str:
    """Accept a prompt that holds the tokens v3 required."""
    if missing := [token for token in TOKENS if token not in prompt]:
        msg = f"the prompt lacks {', '.join(missing)}"
        raise ValueError(msg)
    return prompt


class Board(Model):
    """One announcement board: what v3's AnnouncementType, URL map and channel enum held."""

    model_config = HIDDEN

    # The key of the board's posted list in the store (v3's enum names, so that v3's lists can be
    # imported) and its name in the logs.
    name: Annotated[str, StringConstraints(pattern=r"\S")]
    url: Annotated[str, AfterValidator(_page_url)]  # the board's first page
    layout: Layout
    channel_id: Annotated[PositiveInt, Field(alias="channel-id")]  # where its posts go
    # Only the titles that start with it are posted (v3's filter of STUDENT_MAIN_OFFICE).
    title_prefix: Annotated[str, Field(alias="title-prefix")] = ""


class Config(Model):
    """``plugins/NtustAnnouncements/config.yaml``, with v3's kebab-case keys.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin. The
    bundled file holds v3's example keys and 0 for every channel, so the plugin waits for the
    operator. The model settings that v3 hard-coded are keys with v3's values as defaults; fields
    that a later validator reads come first (``api_format`` before ``model``, ``request_timeout``
    before ``connect_timeout``), so that its error names its own key.
    """

    model_config = HIDDEN

    # Seconds between a board's passes.
    fetch_interval: Annotated[
        int, Field(alias="fetch-interval", ge=MIN_INTERVAL, le=JAVA_LONG_MAX)
    ] = 3600
    api_keys: Annotated[
        tuple[Annotated[str, AfterValidator(_key)], ...],
        Field(alias="api-keys"),
        AfterValidator(_some_keys),
    ]
    prompt: Annotated[str, AfterValidator(_prompt)]  # required, as in v3
    # The model settings (``api.Api``, ``conversion.Limits``), v3's values by default.
    api_format: Annotated[ApiFormat, Field(alias="api-format")] = ApiFormat.GEMINI
    endpoint: Annotated[str, AfterValidator(_endpoint)] = GEMINI_ENDPOINT
    model: str = GEMINI_MODEL  # v3's hard-coded model; checked against the format below
    temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)] | None = TEMPERATURE
    max_output_tokens: Annotated[
        Annotated[int, Field(ge=1, le=MAX_OUTPUT_TOKENS)] | None, Field(alias="max-output-tokens")
    ] = None
    request_timeout: Annotated[
        float, Field(alias="request-timeout", gt=0, le=MAX_TIMEOUT, allow_inf_nan=False)
    ] = REQUEST_TIMEOUT
    connect_timeout: Annotated[
        float, Field(alias="connect-timeout", gt=0, le=MAX_TIMEOUT, allow_inf_nan=False)
    ] = CONNECT_TIMEOUT
    rate_limit: Annotated[int, Field(alias="rate-limit", ge=1, le=MAX_RATE_LIMIT)] = PER_WINDOW
    rate_window: Annotated[float, Field(alias="rate-window", gt=0, le=DAY, allow_inf_nan=False)] = (
        WINDOW
    )
    max_attempts: Annotated[int, Field(alias="max-attempts", ge=1, le=MOST_ATTEMPTS)] = MAX_ATTEMPTS
    retry_waits: Annotated[
        tuple[Annotated[float, Field(ge=0, le=DAY, allow_inf_nan=False)], ...],
        Field(alias="retry-waits", max_length=MOST_WAITS),
        AfterValidator(_some_waits),
    ] = BACKOFF
    boards: tuple[Board, ...]

    @field_validator("model")
    @classmethod
    def _model(cls, model: str, info: ValidationInfo) -> str:
        """Refuse a model that the format cannot send: the gemini format puts it in the path."""
        if not MODEL.fullmatch(model):
            msg = "must be 1 to 256 characters without whitespace"
            raise ValueError(msg)
        if info.data.get("api_format") is ApiFormat.GEMINI and not GEMINI_MODEL_NAME.fullmatch(
            model
        ):
            msg = "the gemini format takes letters, digits, '.', '-' and '_'"
            raise ValueError(msg)
        return model

    @field_validator("connect_timeout")
    @classmethod
    def _connect_timeout(cls, seconds: float, info: ValidationInfo) -> float:
        """Refuse a connect limit beyond the request's, which already ends the attempt."""
        total = info.data.get("request_timeout")
        if total is not None and seconds > total:
            msg = "must not exceed request-timeout"
            raise ValueError(msg)
        return seconds

    @property
    def api(self) -> Api:
        """The settings of the model's API, for ``web.open_web``."""
        return Api(
            self.api_format,
            self.endpoint,
            self.model,
            self.temperature,
            self.max_output_tokens,
            self.request_timeout,
            self.connect_timeout,
        )

    @property
    def limits(self) -> Limits:
        """Each key's rate limit and the retries, for ``conversion.Converter``."""
        return Limits(self.rate_limit, self.rate_window, self.max_attempts, self.retry_waits)

    @field_validator("boards")
    @classmethod
    def _unique_names(cls, boards: tuple[Board, ...]) -> tuple[Board, ...]:
        """Refuse no boards, and two boards with one name: they would share a posted list.

        A check after the items', unlike pydantic's ``min_length``, which counts the items that
        validated and would call 18 boards without channels an empty list.
        """
        if not boards:
            msg = "list at least one board"
            raise ValueError(msg)
        names: set[str] = set()
        for board in boards:
            if board.name in names:
                msg = f"two boards are named {board.name}"
                raise ValueError(msg)
            names.add(board.name)
        return boards
