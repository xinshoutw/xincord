"""The Discord messages of an announcement: v3's header, split and title links.

v3 measured Discord's limits with Kotlin's ``String.length``, in UTF-16 code units, where a
character outside the BMP counts twice; so do these functions, which never cut such a character.
"""

import re
from bisect import bisect_right
from itertools import accumulate
from typing import TYPE_CHECKING
from urllib.parse import quote

from .strings import trim

if TYPE_CHECKING:
    from collections.abc import Iterable

HEADER = chr(0xFF3F) * 15  # v3's 15 FULLWIDTH LOW LINEs before an announcement
MESSAGE_LIMIT = 2000  # Discord's limit for a message's content
SINGLE_LIMIT = 1990 - len(HEADER)  # v3: content up to this length goes in one message
PART_LIMIT = 1980  # v3's parts, after the header's line in the first message
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"
ESCAPED = frozenset("\\[]")  # what ends or breaks a Markdown link's text
ENCODED = frozenset("()<>\\")  # what ends or breaks a Markdown link's URL, with whitespace
BMP_END = 0xFFFF
# A Markdown heading, or a line wholly in bold: the prompt's small headings.
HEADING = re.compile(r"#{1,6} .*|\*\*[^*]+\*\*")
LIST_ITEM = re.compile(r"\s*(?:[-*+\N{BULLET}]|\d+[.)]) ")  # a bullet or a numbered item
# How a break before a line ranks, by that line: a heading, a blank line before it, a list item,
# any other line.
BEFORE_HEADING, AT_BLANK_LINE, BEFORE_LIST_ITEM, AT_LINE_BREAK = range(4)


def _size(character: str) -> int:
    return 2 if ord(character) > BMP_END else 1


def units(text: str) -> int:
    """The length of ``text`` in UTF-16 code units, as Kotlin's ``String.length`` counts it."""
    return sum(_size(character) for character in text)


def _fitting(sizes: Iterable[int], limit: int) -> int:
    """How many of the pieces that have these ``sizes``, from the first, fit in ``limit`` units."""
    return bisect_right(list(accumulate(sizes)), limit)


def clip(text: str, limit: int) -> str:
    """The longest start of ``text`` that fits in ``limit`` units, in whole characters."""
    return text[: _fitting(map(_size, text), limit)]


def split(content: str, limit: int) -> list[str]:
    """``content`` in parts of at most ``limit`` units, cut at its structure.

    Each part ends at the best break among those that fit (:func:`_cut`), else at the limit,
    before a character that would straddle it. The line breaks at a cut are left out, and so are
    parts of only whitespace. Without headings, blank lines or list items, the parts are v3's
    (``splitContentIntoSegments``): each ends before the last line break that fits.
    """
    if units(content) <= limit:
        return [content]
    parts: list[str] = []
    rest = content
    while units(rest) > limit:
        fitting = _fitting(map(_size, rest), limit)
        end, start = _cut(rest, fitting)
        parts.append(rest[:end].rstrip("\n"))
        rest = rest[start:].lstrip("\n")
    parts.append(rest)  # never empty: it was longer than the limit before its last cut
    # A cut between line breaks or spaces can leave a part of only whitespace, which Discord
    # refuses; a refused later part would end the post.
    return [part for part in parts if trim(part)]


def _rank(line: str, *, blank: bool) -> int:
    """How a break before ``line`` ranks: before a heading, at a blank line, before a list item."""
    if HEADING.fullmatch(line.strip()):
        return BEFORE_HEADING
    if blank:
        return AT_BLANK_LINE
    return BEFORE_LIST_ITEM if LIST_ITEM.match(line) else AT_LINE_BREAK


def _cut(text: str, fitting: int) -> tuple[int, int]:
    """Where the part of ``text`` ends and where the rest starts; the part fits in ``fitting``.

    A break before a line ranks by that line (:func:`_rank`); the best rank among the breaks past
    half of ``fitting`` wins, the latest of it, so that a heading near the start makes no tiny
    part; when none is past half, the latest break; when none fits, the limit. A break right after
    a heading never counts: the heading goes to the next part with its text.
    """
    best: dict[int, tuple[int, int]] = {}  # the latest break past half, by rank
    latest: tuple[int, int] | None = None
    end = -1  # where the last line of text ended
    heading = False  # whether that line is a heading
    blank = False  # whether an empty line came after it
    position = 0
    for line in text.split("\n"):
        if not line.strip():
            blank = True
        elif end > fitting:
            break
        else:
            if end > 0 and not heading:
                latest = (end, position)
                if end >= fitting // 2:
                    best[_rank(line, blank=blank)] = latest
            end, heading, blank = position + len(line), bool(HEADING.fullmatch(line.strip())), False
        position += len(line) + 1
    if best:
        return best[min(best)]
    return latest or (fitting, fitting)


def content_messages(content: str) -> list[str]:
    """The messages that post the model's ``content``, as v3's ``createDiscordMessages``.

    The content is trimmed as Kotlin's ``trim()``; up to 1975 units it follows the header in one
    message, else it is split in parts of 1980 units, the header before the first.
    """
    full = trim(content)
    if units(full) <= SINGLE_LIMIT:
        return [f"{HEADER}\n{full}"]
    first, *rest = split(full, PART_LIMIT)
    return [f"{HEADER}\n{first}", *rest]


def link_message(title: str, url: str) -> str:
    """The message that posts an announcement as its title, linked to ``url``.

    v3's ``HEADER + "\\n# [" + title + "](" + url.trim() + ")"``, with ``\\``, ``[`` and ``]``
    escaped in the title and the characters that end a link percent-encoded in the URL, which v3
    sent as they were; a title too long for Discord is cut with an ellipsis, the URL kept whole.
    A URL that leaves no room for a title (no board has one) is posted bare, cut to the limit.
    """
    target = "".join(
        quote(character, safe="") if character in ENCODED or character.isspace() else character
        for character in trim(url)
    )
    prefix = f"{HEADER}\n# ["
    suffix = f"]({target})"
    room = MESSAGE_LIMIT - units(prefix) - units(suffix)
    pieces = [f"\\{character}" if character in ESCAPED else character for character in title]
    sizes = [units(piece) for piece in pieces]
    if sum(sizes) <= room:
        return prefix + "".join(pieces) + suffix
    budget = room - units(ELLIPSIS)
    if budget < 0:
        return clip(f"{HEADER}\n{target}", MESSAGE_LIMIT)
    return prefix + "".join(pieces[: _fitting(sizes, budget)]) + ELLIPSIS + suffix
