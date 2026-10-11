"""The builder's changes to a draft, from its modals and buttons."""

from dataclasses import replace
from typing import TYPE_CHECKING

from .inputs import is_http_url, trim, winner_count
from .model import Policy, Prize
from .times import parse_end_time

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import tzinfo

    from .model import Draft


def submit(
    draft: Draft, sub_action: str, values: Mapping[str, str], now: int, zone: tzinfo | None
) -> Draft | str:
    """The draft that the submitted modal ``sub_action`` makes, or the key of its error.

    Each value is trimmed (``trim``); a missing input is empty. The title must not be
    blank; an empty description, sponsor or thumbnail clears it; the end time must be given, valid
    and later than ``now``; a prize needs a name and a winner count from 1 to 50 and is appended;
    a thumbnail must be an http or https URL. An unknown modal changes nothing.
    """

    def value(key: str) -> str:
        return trim(values.get(key, ""))

    match sub_action:
        case "set-title":
            title = value("title")
            changed = replace(draft, title=title) if title else "error.title"
        case "set-description":
            changed = replace(draft, description=value("description"))
        case "set-end-time":
            changed = _end_time(draft, value("end-time"), now, zone)
        case "add-prize":
            changed = _prize(draft, value("prize-name"), value("winner-count"))
        case "set-sponsor":
            changed = replace(draft, sponsor=value("sponsor"))
        case "set-thumbnail":
            url = value("thumbnail")
            valid = not url or is_http_url(url)
            changed = replace(draft, thumbnail_url=url) if valid else "error.thumbnail"
        case _:
            changed = draft
    return changed


def _prize(draft: Draft, name: str, count_text: str) -> Draft | str:
    """The draft with the prize appended, or the error: no name, or a count outside 1 to 50."""
    count = winner_count(count_text)
    if not name:
        return "error.prize-name"
    if count is None:
        return "error.winner-count"
    return replace(draft, prizes=(*draft.prizes, Prize(name, count)))


def _end_time(draft: Draft, text: str, now: int, zone: tzinfo | None) -> Draft | str:
    """The draft ending at ``text``, or the error: none given, an invalid time or a past one."""
    if not text:
        return "error.end-time"
    end = parse_end_time(text, zone)
    if end is None:
        return "error.end-time-format"
    if end <= now:
        return "error.end-time-past"
    return replace(draft, end_at=end)


def remove_last_prize(draft: Draft) -> Draft | None:
    """The draft without its last prize, or None when it has none."""
    return replace(draft, prizes=draft.prizes[:-1]) if draft.prizes else None


def switch_policy(draft: Draft) -> Draft:
    """The draft with the other winner policy."""
    unique = draft.policy is Policy.ALLOW_DUPLICATE
    return replace(draft, policy=Policy.UNIQUE_ACROSS_PRIZES if unique else Policy.ALLOW_DUPLICATE)


def problem(draft: Draft, now: int) -> str | None:
    """The key of the text for what the draft lacks to be posted at ``now``, in this order.

    A title, then an end time later than ``now``, then a prize; None when it has them all.
    """
    if not trim(draft.title):
        return "error.no-title"
    if draft.end_at <= now:
        return "error.no-end-time"
    return None if draft.prizes else "error.no-prizes"
