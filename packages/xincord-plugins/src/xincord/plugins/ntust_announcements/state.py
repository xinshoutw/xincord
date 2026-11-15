"""The feed's position and the announcements waiting to be posted, in the store as one document.

Namespace ``NtustAnnouncements.feed``, key ``state``:
``{"after": int, "waiting": [{"id": int, "due": ISO 8601, "posted": [channel IDs]}]}``.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from xincord.core.storage import JSON, Store

NAMESPACE = "NtustAnnouncements.feed"
KEY = "state"


class DataError(Exception):
    """The document is of another shape; it is left as it is."""


@dataclass(frozen=True)
class Waiting:
    """An announcement waiting for its rewrite or for a channel to take it."""

    id: int
    due: datetime  # when it is posted, rewritten or not
    posted: tuple[int, ...] = ()  # the channels that got it


@dataclass(frozen=True)
class State:
    """The last event read and the waiting announcements, in the order they came."""

    after: int
    waiting: tuple[Waiting, ...] = ()


def parse_state(document: JSON) -> State:
    """The state of a stored document.

    Raises:
        DataError: The document is not of the state's shape.
    """
    raise NotImplementedError


def state_document(state: State) -> dict[str, JSON]:
    """The document of ``state``."""
    raise NotImplementedError


@dataclass(frozen=True)
class States:
    """The state in the store."""

    store: Store

    async def load(self) -> State | None:
        """The stored state, or None before the first read.

        Raises:
            DataError: The document is of another shape.
        """
        raise NotImplementedError

    async def save(self, state: State) -> None:
        """Store ``state``."""
        raise NotImplementedError
