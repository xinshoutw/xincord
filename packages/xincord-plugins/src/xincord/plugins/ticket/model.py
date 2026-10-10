"""A panel button's stored entry, v3's ``DataContainer``, and its JSON as v3's Moshi wrote it.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/json/serializer/JsonData.kt:3-10
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

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
    if not isinstance(value, dict):
        msg = f"{where}: the entry is not a JSON object: {value!r}"
        raise DataError(msg)
    reason_title = value.get("reasonTitle")
    admin_ids = value.get("adminIds")
    category_id = value.get("categoryId")
    if not isinstance(reason_title, str):
        msg = f"{where}: reasonTitle is not text: {reason_title!r}"
        raise DataError(msg)
    if not isinstance(admin_ids, list) or not all(_is_integer(item) for item in admin_ids):
        msg = f"{where}: adminIds is not a list of IDs: {admin_ids!r}"
        raise DataError(msg)
    if not _is_integer(category_id):
        msg = f"{where}: categoryId is not an ID: {category_id!r}"
        raise DataError(msg)
    return Entry(reason_title, tuple(cast("list[int]", admin_ids)), cast("int", category_id))


def entry_json(entry: Entry) -> dict[str, JSON]:
    """The entry as v3's Moshi wrote it, in its field order."""
    return {
        "reasonTitle": entry.reason_title,
        "adminIds": list(entry.admin_ids),
        "categoryId": entry.category_id,
    }


def _is_integer(value: JSON) -> bool:
    """Whether ``value`` is a JSON integer, which Moshi read as a Kotlin ``Long``; not a boolean."""
    return isinstance(value, int) and not isinstance(value, bool)
