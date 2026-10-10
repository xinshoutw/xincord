"""The plugin's ``config.yaml``: v3's keys, and the boards, channels and model that v3 hard-coded.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/config/ConfigSerializer.kt:6-26
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:33-36
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:220-238
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:31-115
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementTypes.kt:24-45
"""

from enum import StrEnum
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    field_validator,
)

from xincord.core.config import Model

JAVA_LONG_MAX = 2**63 - 1  # v3's fetch-interval was a Long
MIN_INTERVAL = 60  # v3's minimum, which it checked only while enabled
# v3's placeholder key, which its bundled file held twice and which it refused while enabled.
EXAMPLE_KEY = "sk-thisisatestkey1234567890abcdef1234567890"
# The tokens that v3's validateConfiguration required; {{page_title}} was optional.
TOKENS = ("{{page_url}}", "{{base_url}}", "{{now}}", "{{html}}")
SCHEMES = frozenset({"http", "https"})
# pydantic's errors show no input: the core logs them with their traceback, and keys are secrets.
HIDDEN = ConfigDict(hide_input_in_errors=True)


class Layout(StrEnum):
    """How a board's first page lists its entries: v3's three parsers."""

    STUDENT_AFFAIRS = "student-affairs"  # a table, the title link in each row's first cell
    ACADEMIC_AFFAIRS = "academic-affairs"  # a table, the title link in each row's second cell
    LANGUAGE_CENTER = "language-center"  # rows of divisions, one title link each


def _key(key: str) -> str:
    """Accept a Gemini API key; the messages never quote it."""
    if not key.strip():
        msg = "must not be blank"
        raise ValueError(msg)
    if key == EXAMPLE_KEY:
        msg = "replace the example key with a Gemini API key"
        raise ValueError(msg)
    return key


def _page_url(url: str) -> str:
    """Accept an http or https URL with a host and no spaces, such as a board's first page."""
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises ValueError unless the port is a number from 0 to 65535
    except ValueError:
        parts = None
    if (
        parts is None
        or parts.scheme not in SCHEMES
        or not parts.hostname
        or any(character.isspace() for character in url)
    ):
        msg = "must be an http or https URL with a host and no spaces"
        raise ValueError(msg)
    return url


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
    operator.
    """

    model_config = HIDDEN

    # Seconds between a board's passes.
    fetch_interval: Annotated[
        int, Field(alias="fetch-interval", ge=MIN_INTERVAL, le=JAVA_LONG_MAX)
    ] = 3600
    api_keys: Annotated[
        tuple[Annotated[str, AfterValidator(_key)], ...], Field(alias="api-keys", min_length=1)
    ]
    prompt: Annotated[str, AfterValidator(_prompt)]  # required, as in v3
    # v3's hard-coded model; it goes into the request's path.
    model: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]+$")] = "gemini-2.5-flash"
    boards: Annotated[tuple[Board, ...], Field(min_length=1)]

    @field_validator("boards")
    @classmethod
    def _unique_names(cls, boards: tuple[Board, ...]) -> tuple[Board, ...]:
        """Refuse two boards with one name: they would share a posted list."""
        names: set[str] = set()
        for board in boards:
            if board.name in names:
                msg = f"two boards are named {board.name}"
                raise ValueError(msg)
            names.add(board.name)
        return boards
