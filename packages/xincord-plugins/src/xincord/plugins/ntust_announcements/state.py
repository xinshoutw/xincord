"""The feed's position and the announcements waiting to be posted, in the store as one document.

Namespace ``NtustAnnouncements.feed``, key ``state``:
``{"after": int, "waiting": [{"id": int, "due": ISO 8601, "posted": [channel IDs]}]}``.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
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
    fields = cast("dict[str, JSON]", document) if isinstance(document, dict) else {}
    after = _integer(fields.get("after"))
    waiting = fields.get("waiting", [])
    if after is None or not isinstance(waiting, list):
        msg = "not the feed's state: expected an object with an integer after and a waiting list"
        raise DataError(msg)
    return State(after, tuple(_waiting(entry) for entry in waiting))


def _integer(value: JSON) -> int | None:
    """``value`` if it is an integer; JSON's true and false are not."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _due(value: JSON) -> datetime | None:
    """``value`` as an ISO 8601 time with its offset, or None."""
    if not isinstance(value, str):
        return None
    try:
        due = datetime.fromisoformat(value)
    except ValueError:
        return None
    return due if due.tzinfo is not None else None


def _waiting(entry: JSON) -> Waiting:
    """A waiting announcement of the document.

    Raises:
        DataError: The entry is not an object with an integer id, an ISO 8601 due time with its
            offset and a list of channel IDs.
    """
    fields = cast("dict[str, JSON]", entry) if isinstance(entry, dict) else {}
    number, due, posted = _integer(fields.get("id")), _due(fields.get("due")), fields.get("posted")
    channels = [_integer(channel) for channel in posted] if isinstance(posted, list) else [None]
    if number is None or due is None or None in channels:
        msg = "not the feed's state: a waiting announcement lacks an id, a due time or channels"
        raise DataError(msg)
    return Waiting(number, due, tuple(cast("list[int]", channels)))


def state_document(state: State) -> dict[str, JSON]:
    """The document of ``state``."""
    waiting: list[JSON] = [
        {"id": entry.id, "due": entry.due.isoformat(), "posted": list(entry.posted)}
        for entry in state.waiting
    ]
    return {"after": state.after, "waiting": waiting}


@dataclass(frozen=True)
class States:
    """The state in the store."""

    store: Store

    async def load(self) -> State | None:
        """The stored state, or None before the first read.

        Raises:
            DataError: The document is of another shape.
        """
        document = await self.store.get(NAMESPACE, KEY)
        return None if document is None else parse_state(document)

    async def save(self, state: State) -> None:
        """Store ``state``."""
        await self.store.put(NAMESPACE, KEY, state_document(state))
