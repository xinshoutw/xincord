"""The feed's stored state: its document, read back as it was written."""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from bulletin_fakes import NOW
from xincord.plugins.ntust_announcements.state import (
    KEY,
    NAMESPACE,
    DataError,
    State,
    States,
    Waiting,
    parse_state,
)

if TYPE_CHECKING:
    from xincord.core.storage import Store

XFAIL = pytest.mark.xfail(strict=True, reason="read-bulletin-feed")
STATE = State(7, (Waiting(1, NOW, (101,)), Waiting(2, NOW + timedelta(hours=1))))
DOCUMENT: dict[str, object] = {
    "after": 7,
    "waiting": [
        {"id": 1, "due": "2026-11-16T01:00:00+00:00", "posted": [101]},
        {"id": 2, "due": "2026-11-16T02:00:00+00:00", "posted": []},
    ],
}

# Documents of other shapes.
BROKEN: list[object] = [
    [],
    {},
    {"after": "7"},
    {"after": True},
    {"after": 7, "waiting": {}},
    {"after": 7, "waiting": [7]},
    {"after": 7, "waiting": [{"id": 1}]},
    {"after": 7, "waiting": [{"id": 1, "due": "soon", "posted": []}]},
    {"after": 7, "waiting": [{"id": 1, "due": "2026-11-16T01:00:00", "posted": []}]},
    {
        "after": 7,
        "waiting": [{"id": 1, "due": "2026-11-16T01:00:00+00:00", "posted": ["1"]}],
    },
]


@XFAIL
async def test_stored_as_a_document(store: Store) -> None:
    """Requirement: The feed's position and the waiting announcements are stored."""
    await States(store).save(STATE)

    assert await store.get(NAMESPACE, KEY) == DOCUMENT
    assert await States(store).load() == STATE


@XFAIL
async def test_nothing_stored(store: Store) -> None:
    """Requirement: The first read starts at the feed's end."""
    assert await States(store).load() is None


@XFAIL
def test_no_waiting_list() -> None:
    """Requirement: The feed's position and the waiting announcements are stored."""
    assert parse_state({"after": 3}) == State(3)


@XFAIL
@pytest.mark.parametrize("document", BROKEN)
def test_another_shape(document: object) -> None:
    """Requirement: The feed's position and the waiting announcements are stored."""
    with pytest.raises(DataError):
        parse_state(document)  # pyright: ignore[reportArgumentType]
