"""The Discord messages of an announcement: v3's header, split and title links.

v3 measured Discord's limits with Kotlin's ``String.length``, in UTF-16 code units, where a
character outside the BMP counts twice; so do these functions, which never cut such a character.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:97-183
"""

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
    """``content`` in parts of at most ``limit`` units, as v3's ``splitContentIntoSegments``.

    A part ends before the last line break that fits, which no part keeps; a line break at the
    part's start does not count, as in v3, and without one the part is cut at the limit, before a
    character that would straddle it. Parts of only whitespace are left out.
    """
    if units(content) <= limit:
        return [content]
    parts: list[str] = []
    rest = content
    while units(rest) > limit:
        fitting = _fitting(map(_size, rest), limit)
        cut = rest.rfind("\n", 0, fitting + 1)
        if cut > 0:
            parts.append(rest[:cut])
            rest = rest[cut + 1 :]
        else:
            parts.append(rest[:fitting])
            rest = rest[fitting:]
    parts.append(rest)  # never empty: it was longer than the limit before its last cut
    # A cut between line breaks or spaces can leave a part of only whitespace, which Discord
    # refuses; a refused later part would end the post.
    return [part for part in parts if trim(part)]


def content_messages(content: str) -> list[str]:
    """The messages that post Gemini's ``content``, as v3's ``createDiscordMessages``.

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
