"""The plugin's ``config.yaml``: the interval, the keys, the prompt, the boards and the model."""

import re
from enum import StrEnum
from importlib.resources import files
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlsplit

import yaml
from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    ValidationInfo,
    field_validator,
)
from yarl import URL

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

INTERVAL_MAX = 2**63 - 1  # a 64-bit integer
MIN_INTERVAL = 60
# The example key, which the bundled file holds twice and which the config refuses.
EXAMPLE_KEY = "sk-thisisatestkey1234567890abcdef1234567890"
# The tokens that the prompt needs; {{page_title}} is optional.
TOKENS = ("{{page_url}}", "{{base_url}}", "{{now}}", "{{html}}")
REVIEW_TOKENS = ("{{html}}", "{{markdown}}")  # what the second check needs
FENCE = "```"  # refused by default: the model wrapped its posts in code fences
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
    """How a board's first page lists its entries: three layouts."""

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
    """Accept the model's API: an http or https URL with a host and a port from 1 to 65535, without
    user info, a query, a fragment or spaces.

    It is read as aiohttp reads it (yarl, which refuses a backslash in the host where
    ``urlsplit`` takes it), so that every endpoint that loads can be requested. Each format
    appends its path, and keys belong in ``api-keys``; a final ``/`` is dropped. The message never
    quotes the URL, whose path can hold a proxy's token.
    """
    try:
        parsed = URL(url)
    except ValueError:
        raise ValueError(ENDPOINT) from None
    authority = url.partition("://")[2].partition("/")[0]
    if (
        parsed.scheme not in SCHEMES
        or not parsed.host
        or parsed.explicit_port == 0
        or "@" in authority
        or any(character in "?#" or character.isspace() for character in url)
    ):
        raise ValueError(ENDPOINT)
    return url.rstrip("/")


def _some_waits(waits: tuple[float, ...]) -> tuple[float, ...]:
    """Refuse an empty list of waits: after the first failed attempt, a conversion waits."""
    if not waits:
        msg = "list at least one wait"
        raise ValueError(msg)
    return waits


def _prompt(prompt: str) -> str:
    """Accept a prompt that holds the tokens it needs."""
    if missing := [token for token in TOKENS if token not in prompt]:
        msg = f"the prompt lacks {', '.join(missing)}"
        raise ValueError(msg)
    return prompt


def _review_prompt(prompt: str | None) -> str | None:
    """Accept a review prompt that holds the article and the conversion under review."""
    if prompt is not None and (
        missing := [token for token in REVIEW_TOKENS if token not in prompt]
    ):
        msg = f"the review prompt lacks {', '.join(missing)}"
        raise ValueError(msg)
    return prompt


def bundled_review_prompt() -> str:
    """The bundled ``config.yaml``'s ``review-prompt``, for operator files without one.

    The text is zh-TW copy, which a Python file cannot hold.
    """
    text = files(__package__).joinpath("config.yaml").read_text(encoding="utf-8")
    bundled: dict[str, str] = yaml.safe_load(text)
    return bundled["review-prompt"]


class Board(Model):
    """One announcement board: its name, page, layout, channel and title prefix."""

    model_config = HIDDEN

    # The key of the board's posted list in the store and its name in the logs.
    name: Annotated[str, StringConstraints(pattern=r"\S")]
    url: Annotated[str, AfterValidator(_page_url)]  # the board's first page
    layout: Layout
    channel_id: Annotated[PositiveInt, Field(alias="channel-id")]  # where its posts go
    # Only the titles that start with it are posted.
    title_prefix: Annotated[str, Field(alias="title-prefix")] = ""


class Config(Model):
    """``plugins/NtustAnnouncements/config.yaml``, with kebab-case keys.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns. The
    bundled file holds example keys and 0 for every channel, so the plugin waits for the operator.
    The model settings have defaults; fields
    that a later validator reads come first (``api_format`` before ``model``, ``request_timeout``
    before ``connect_timeout``), so that its error names its own key.
    """

    model_config = HIDDEN

    # Seconds between a board's passes.
    fetch_interval: Annotated[
        int, Field(alias="fetch-interval", ge=MIN_INTERVAL, le=INTERVAL_MAX)
    ] = 3600
    api_keys: Annotated[
        tuple[Annotated[str, AfterValidator(_key)], ...],
        Field(alias="api-keys"),
        AfterValidator(_some_keys),
    ]
    prompt: Annotated[str, AfterValidator(_prompt)]  # required
    # Answers that hold one of these fail and are asked again; none may be empty.
    reject_texts: Annotated[
        tuple[Annotated[str, StringConstraints(min_length=1)], ...], Field(alias="reject-texts")
    ] = (FENCE,)
    reviewers: tuple[PositiveInt, ...] = ()  # users whose cross mark redoes a post
    # The second check of a redone post; None: the bundled file's (``bundled_review_prompt``).
    review_prompt: Annotated[
        str | None, Field(alias="review-prompt"), AfterValidator(_review_prompt)
    ] = None
    # The model settings (``api.Api``, ``conversion.Limits``), with defaults.
    api_format: Annotated[ApiFormat, Field(alias="api-format")] = ApiFormat.GEMINI
    endpoint: Annotated[str, AfterValidator(_endpoint)] = GEMINI_ENDPOINT
    model: str = GEMINI_MODEL  # checked against the format below
    # Strict numbers: YAML reads yes, on and true as true, which a lax number takes as 1.
    temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False, strict=True)] | None = (
        TEMPERATURE
    )
    max_output_tokens: Annotated[
        Annotated[int, Field(ge=1, le=MAX_OUTPUT_TOKENS, strict=True)] | None,
        Field(alias="max-output-tokens"),
    ] = None
    request_timeout: Annotated[
        float,
        Field(alias="request-timeout", gt=0, le=MAX_TIMEOUT, allow_inf_nan=False, strict=True),
    ] = REQUEST_TIMEOUT
    connect_timeout: Annotated[
        float,
        Field(alias="connect-timeout", gt=0, le=MAX_TIMEOUT, allow_inf_nan=False, strict=True),
    ] = CONNECT_TIMEOUT
    rate_limit: Annotated[int, Field(alias="rate-limit", ge=1, le=MAX_RATE_LIMIT, strict=True)] = (
        PER_WINDOW
    )
    rate_window: Annotated[
        float, Field(alias="rate-window", gt=0, le=DAY, allow_inf_nan=False, strict=True)
    ] = WINDOW
    max_attempts: Annotated[
        int, Field(alias="max-attempts", ge=1, le=MOST_ATTEMPTS, strict=True)
    ] = MAX_ATTEMPTS
    retry_waits: Annotated[
        tuple[Annotated[float, Field(ge=0, le=DAY, allow_inf_nan=False, strict=True)], ...],
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
