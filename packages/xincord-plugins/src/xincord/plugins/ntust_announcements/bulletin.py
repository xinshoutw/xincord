"""bulletin's public API: its events feed and one announcement, over one aiohttp session.

The answers are validated: only the fields that the plugin uses are read, and any other shape is
an :class:`AnswerError`.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import aiohttp
from pydantic import AwareDatetime, BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

PAGE = 500  # events per read: the API's most
OK = 200
NOT_FOUND = 404
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


class FetchError(Exception):
    """The API answered with a status other than 200."""

    def __init__(self, status: int) -> None:
        """Keep the status."""
        super().__init__(f"code {status}")
        self.status = status


class AnswerError(Exception):
    """The API answered 200 with a body of another shape."""


class Answer(BaseModel):
    """A part of an answer: frozen, other fields ignored."""

    model_config = ConfigDict(frozen=True)


class Rendition(Answer):
    """bulletin's rewrite; the feed's items give no Markdown, one announcement does."""

    markdown: str | None = None


class Attachment(Answer):
    """An attachment's name and its URL at the school."""

    name: str
    url: str


class Item(Answer):
    """An announcement as the feed lists it."""

    id: int
    url: str
    link_item: bool  # a link to another page, never rewritten
    title: str
    boards: tuple[str, ...]  # `<site>-<board>`
    rendition: Rendition | None = None


class Announcement(Item):
    """One announcement, with its rewrite's Markdown and its attachments."""

    attachments: tuple[Attachment, ...] = ()


class Event(Answer):
    """What happened to an announcement; ``kind`` stays text, so new kinds are only ignored."""

    id: int
    kind: str
    notify: bool
    at: AwareDatetime
    announcement: Item


class Events(Answer):
    """A read of the feed: its events in ID order, and the last ID, ``after`` when none."""

    events: tuple[Event, ...]
    last: int


class Api(Protocol):
    """What the plugin asks of bulletin: :class:`Bulletin`, or a fake in tests."""

    async def events(self, after: int) -> Events:
        """Up to ``PAGE`` events after the event ``after``."""
        ...

    async def announcement(self, announcement_id: int) -> Announcement | None:
        """One announcement, or None when the API has none with that ID."""
        ...


@dataclass(frozen=True)
class Bulletin:
    """The API at ``url``, such as ``https://bulletin.ntust.org/api/v1``."""

    session: aiohttp.ClientSession
    url: str

    async def events(self, after: int) -> Events:
        """Up to ``PAGE`` events after the event ``after``.

        Raises:
            FetchError: The API answered with a status other than 200.
            AnswerError: The answer is not the feed's JSON.
        """
        raise NotImplementedError

    async def announcement(self, announcement_id: int) -> Announcement | None:
        """One announcement, or None when the API answers 404.

        Raises:
            FetchError: The API answered with a status other than 200 or 404.
            AnswerError: The answer is not an announcement's JSON.
        """
        raise NotImplementedError


@asynccontextmanager
async def open_bulletin(url: str) -> AsyncGenerator[Bulletin]:
    """A session for the API at ``url``, closed when the block ends."""
    async with aiohttp.ClientSession() as session:
        yield Bulletin(session, url)
