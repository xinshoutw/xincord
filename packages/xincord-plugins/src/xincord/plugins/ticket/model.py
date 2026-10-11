"""A builder's draft, a panel button's stored entry and its JSON."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from xincord.core.storage import JSON


class DataError(Exception):
    """A stored document or entry is of another shape; the message names it."""


@dataclass(frozen=True)
class Entry:
    """What a panel button opens: its reason title, its staff roles and its category (0: the
    panel channel's)."""

    reason_title: str
    admin_ids: tuple[int, ...]
    category_id: int


GREEN = 3  # Discord's success style, a panel button's default
COLOR = re.compile(r"(?:#|0[xX])?([0-9a-fA-F]{1,6})")  # what the color modal takes


@dataclass(frozen=True)
class Draft:
    """A panel in the builder, with its stored entry's fields.

    Empty texts stand for unset values: no author, icon, title, description, label or
    emoji. ``button_style`` is Discord's button style, 1 to 4; ``category_id`` 0 is the panel
    channel's category.
    """

    reason_title: str
    author: str = ""
    author_icon_url: str = ""
    title: str = ""
    description: str = ""
    color: int = 0x00FFFF
    button_text: str = ""
    button_emoji: str = ""
    button_style: int = GREEN
    admin_ids: tuple[int, ...] = ()
    category_id: int = 0

    def entry(self) -> Entry:
        """What the panel's button stores."""
        return Entry(self.reason_title, self.admin_ids, self.category_id)


@dataclass(frozen=True)
class Controls:
    """What a ticket's control row carries: the ticket's member, and the panel button's message
    and index, whose entry names the staff roles."""

    user_id: int
    message_id: str
    index: str


def hex_color(color: int) -> str:
    """A color as the modal shows it: ``#`` and six uppercase hex digits."""
    return f"#{color & 0xFFFFFF:06X}"


def parse_color(text: str) -> int | None:
    """The color typed in the color modal: one to six hex digits after ``#``, ``0x`` or nothing.

    None when the text is no such color.
    """
    match = COLOR.fullmatch(text.strip())
    return None if match is None else int(match[1], 16)


def parse_entry(value: JSON, where: str) -> Entry:
    """Read a stored entry: every field required, integers exact.

    Raises:
        DataError: ``value`` is of another shape; the message starts with ``where``.
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
    """The entry's stored JSON, in its field order."""
    return {
        "reasonTitle": entry.reason_title,
        "adminIds": list(entry.admin_ids),
        "categoryId": entry.category_id,
    }


def _is_integer(value: JSON) -> bool:
    """Whether ``value`` is a JSON integer, not a boolean."""
    return isinstance(value, int) and not isinstance(value, bool)
