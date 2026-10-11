"""A listen channel's settings: which channels it detects, and how the menu lists them."""

from dataclasses import dataclass
from itertools import accumulate
from typing import TYPE_CHECKING

from xincord.core.placeholders import render

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

FIELD_MAX = 1024  # the longest embed field value Discord takes
MORE = "..."  # follows the lines of a list that do not all fit

# A channel's ID, then the IDs of what holds it, None where nothing does: a channel's category; a
# thread's parent channel and that channel's category.
type ChannelIds = tuple[int, *tuple[int | None, ...]]


@dataclass(frozen=True)
class Setting:
    """v3's ``ChannelData``: the mode and the lists of one listen channel.

    A listen channel without settings is in the allow mode with empty lists, as v3's default. The
    lists keep their order and hold each channel or category ID once (v3's ``LinkedHashSet``).
    """

    allow_mode: bool = True
    allow: tuple[int, ...] = ()
    block: tuple[int, ...] = ()


def detects(setting: Setting, channel_id: int, *parents: int | None) -> bool:
    """Whether ``setting`` detects the channel ``channel_id``, held by ``parents``.

    ``parents`` are a channel's category, or a thread's parent channel and that channel's category
    (None where there is none). In the allow mode, the channel or one of its parents must be
    allowed; in the block mode, none may be blocked. v3 expanded the listed categories into their
    current channels and looked the event's channel up among them, which gives the same answer for
    channels; it never detected a thread through its parent channel.
    """
    sides = {channel_id, *(parent for parent in parents if parent is not None)}
    if setting.allow_mode:
        return not sides.isdisjoint(setting.allow)
    return sides.isdisjoint(setting.block)


def targets(settings: Mapping[int, Setting], channels: Iterable[ChannelIds]) -> list[int]:
    """The listen channels whose settings detect one of ``channels``, each with its parents.

    They keep the settings' order. A voice switch has two channels, and goes to the listen channels
    that detect either, as in v3.
    """
    places = tuple(channels)
    return [
        listen
        for listen, setting in settings.items()
        if any(detects(setting, *place) for place in places)
    ]


def list_text(
    ids: Sequence[int], line: str, empty: str, values: Mapping[str, str], prefix: str
) -> str:
    """v3's list field: ``line`` rendered for each ID, or ``empty`` for an empty list.

    Each line gets ``<prefix>_channel_mention`` and ``<prefix>_channel_id`` (v3 replaced them
    first) and ``values``, in one pass. Lines that do not fit in a field's 1024 characters, counted
    in UTF-16 code units as JDA counted them, are left out, and ``...`` follows the others: v3
    threw there, after saving the list, so the menu never opened again.
    """
    if not ids:
        return render(empty, values)
    lines = [
        render(
            line,
            {
                **values,
                f"{prefix}_channel_mention": f"<#{channel}>",
                f"{prefix}_channel_id": str(channel),
            },
        )
        for channel in ids
    ]
    if units("".join(lines)) <= FIELD_MAX:
        return "".join(lines)
    # The running totals grow, so the lines that fit are the first ones.
    room = FIELD_MAX - units(MORE)
    fitting = sum(1 for total in accumulate(map(units, lines)) if total <= room)
    return "".join(lines[:fitting]) + MORE


def units(text: str) -> int:
    """The length of ``text`` in UTF-16 code units, Java's ``String.length``.

    A character outside the BMP counts twice, so the result never exceeds Discord's limit,
    whichever way Discord counts it.
    """
    return len(text.encode("utf-16-le")) // 2
