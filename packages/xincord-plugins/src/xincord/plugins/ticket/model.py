"""A panel button's stored entry, v3's ``DataContainer``, and its JSON as v3's Moshi wrote it.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/json/serializer/JsonData.kt:3-10
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xincord.core.storage import JSON


class DataError(Exception):
    """A stored document or entry is not v3's shape; the message names it."""


@dataclass(frozen=True)
class Entry:
    """What a panel button opens: its reason title, its staff roles and its category (0: the
    panel channel's)."""

    reason_title: str
    admin_ids: tuple[int, ...]
    category_id: int


def parse_entry(value: JSON, where: str) -> Entry:
    """Read a stored entry as v3's Moshi did: every field required, integers exact.

    Raises:
        DataError: ``value`` is not v3's shape; the message starts with ``where``.
    """
    raise NotImplementedError


def entry_json(entry: Entry) -> dict[str, JSON]:
    """The entry as v3's Moshi wrote it, in its field order."""
    raise NotImplementedError
