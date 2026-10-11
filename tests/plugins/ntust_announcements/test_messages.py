"""The Discord messages of an announcement: the header, the split and the title links."""

import pytest

from xincord.plugins.ntust_announcements.messages import (
    HEADER,
    MESSAGE_LIMIT,
    content_messages,
    link_message,
    split,
    units,
)

FULLWIDTH_LOW_LINE = chr(0xFF3F)
EMOJI = chr(0x1F600)  # outside the BMP: two UTF-16 code units
ELLIPSIS = chr(0x2026)
URL = "https://student.ntust.edu.tw/p/406-1053-152183,r1436.php?Lang=zh-tw"


def line_split(content: str, max_len: int) -> list[str]:
    """A plain split before the last line break that fits, for BMP-only text."""
    if len(content) <= max_len:
        return [content]
    segments: list[str] = []
    rest = content
    while len(rest) > max_len:
        cut = rest.rfind("\n", 0, max_len + 1)
        end = cut if cut > 0 else max_len
        segments.append(rest[:end])
        rest = rest[end + 1 :] if cut > 0 else rest[end:]
    if rest:
        segments.append(rest)
    return segments


def test_header_and_units() -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    assert HEADER == FULLWIDTH_LOW_LINE * 15
    assert units(HEADER) == 15
    assert units(f"a{EMOJI}") == 3


@pytest.mark.parametrize("length", [1, 1975, 1976, 1980])
def test_one_message(length: int) -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    content = "a" * length

    # Up to 1975 units go in one message, the header first.
    assert content_messages(f" \n\t{content}\n ") == [f"{HEADER}\n{content}"]


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("a" * 1500 + "\n" + "b" * 1000, id="one break"),
        pytest.param("a" * 1980 + "\n" + "b" * 10, id="break at the limit"),
        pytest.param("a" * 1981 + "\n" + "b" * 10, id="break past the limit"),
        pytest.param(("line\n" * 900).strip(), id="many lines"),
        pytest.param("a" * 1500 + "\n" + "b" * 3000 + "\n" + "c" * 100, id="long line"),
    ],
)
def test_split_at_a_line_break(content: str) -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    parts = line_split(content, 1980)

    assert split(content, 1980) == parts
    assert content_messages(content) == [f"{HEADER}\n{parts[0]}", *parts[1:]]
    assert all(units(message) <= MESSAGE_LIMIT for message in content_messages(content))


def test_split_without_a_line_break() -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    assert split("a" * 4000, 1980) == ["a" * 1980, "a" * 1980, "a" * 40]
    assert split("a" * 1981, 1980) == ["a" * 1980, "a"]
    # A character outside the BMP that straddles the limit goes to the next part whole, its
    # surrogate pair kept together.
    content = "a" * 1979 + EMOJI + "b" * 100
    assert split(content, 1980) == ["a" * 1979, EMOJI + "b" * 100]
    # Units, not characters: 1000 emoji are 2000 units.
    assert split(EMOJI * 1000, 1980) == [EMOJI * 990, EMOJI * 10]


@pytest.mark.parametrize(
    ("title", "url", "message"),
    [
        pytest.param("Notice", URL, f"{HEADER}\n# [Notice]({URL})", id="plain"),
        pytest.param("Notice", f"  {URL}\n", f"{HEADER}\n# [Notice]({URL})", id="url trimmed"),
        pytest.param(
            "A [draft] notice \\ here",
            URL,
            f"{HEADER}\n# [A \\[draft\\] notice \\\\ here]({URL})",
            id="escaped",
        ),
        pytest.param(
            "Map",
            "https://example.com/a (b)<c>.pdf",
            f"{HEADER}\n# [Map](https://example.com/a%20%28b%29%3Cc%3E.pdf)",
            id="url encoded",
        ),
    ],
)
def test_title_link(title: str, url: str, message: str) -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    assert link_message(title, url) == message


@pytest.mark.parametrize(
    ("title", "kept"),
    [
        pytest.param("t" * 3000, "t", id="letters"),
        pytest.param(EMOJI * 1500, EMOJI, id="emoji"),
        pytest.param("]" * 3000, "\\]", id="escapes"),
    ],
)
def test_long_title(title: str, kept: str) -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    message = link_message(title, URL)

    assert units(message) <= MESSAGE_LIMIT
    assert message.startswith(f"{HEADER}\n# [{kept}")
    # Whole characters and whole escapes, an ellipsis, and the whole URL.
    head, _, tail = message.partition(ELLIPSIS)
    title_part = head.removeprefix(f"{HEADER}\n# [")
    assert tail == f"]({URL})"
    assert title_part == kept * (len(title_part) // len(kept))
    assert units(message) > MESSAGE_LIMIT - units(kept)  # as much as fits


def test_url_without_room() -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    url = "https://example.com/" + "a" * 1990  # no board links such a URL

    message = link_message("Notice", url)

    assert message == f"{HEADER}\n{url}"[:MESSAGE_LIMIT]


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("a" * 1980 + "\n\n\n" + "b" * 3000, id="line breaks"),
        pytest.param("a" * 1975 + "\n" + " " * 10 + "\n" + "b" * 3000, id="spaces"),
    ],
)
def test_no_blank_parts(content: str) -> None:
    """Requirement: Announcements become messages within Discord's limits."""
    messages = content_messages(content)

    # Discord refuses a message of only whitespace, and a refused later part ends the post.
    assert all(message.strip() for message in messages)
    assert "".join(messages).count("b") == 3000


def test_split_before_a_heading() -> None:
    """Requirement: Long content is split at its structure."""
    first = "## A\n" + "x" * 1200 + "\n\n" + "y" * 300
    second = "## B\n" + "z" * 900

    assert split(f"{first}\n{second}", 1980) == [first, second]


def test_split_at_a_blank_line() -> None:
    """Requirement: Long content is split at its structure."""
    first = "a" * 1000 + "\n" + "b" * 500
    second = "c" * 300 + "\n" + "d" * 600

    assert split(f"{first}\n\n{second}", 1980) == [first, second]


def test_split_before_a_list_item() -> None:
    """Requirement: Long content is split at its structure."""
    first = "p" * 1100 + "\n- " + "a" * 400
    second = "1. " + "b" * 400 + "\n" + "c" * 400  # a list item, then its continued line

    assert split(f"{first}\n{second}", 1980) == [first, second]


def test_no_short_parts() -> None:
    """Requirement: Long content is split at its structure."""
    title = "# [Notice](https://student.ntust.edu.tw/p/406-1053-152183.php)"
    items = ["1. " + "a" * 900, "2. " + "b" * 900, "3. " + "c" * 900]
    content = f"{title}\n\n**Notes:**\n\n" + "\n".join(items)

    # The heading and the blank lines fit only in the first half: no part of one line.
    assert split(content, 1980) == [f"{title}\n\n**Notes:**\n\n{items[0]}\n{items[1]}", items[2]]


@pytest.mark.parametrize(
    "heading", [pytest.param("## H", id="heading"), pytest.param("**Notes:**", id="bold line")]
)
def test_heading_kept_with_its_text(heading: str) -> None:
    """Requirement: Long content is split at its structure."""
    content = "x" * 1500 + f"\n{heading}\n" + "y" * 800

    assert split(content, 1980) == ["x" * 1500, f"{heading}\n" + "y" * 800]


def test_consecutive_breaks() -> None:
    """Requirement: Long content is split at its structure."""
    content = "a" * 1979 + "\n\n\n" + "b" * 2500

    # The line breaks at a cut are left out.
    assert split(content, 1980) == ["a" * 1979, "b" * 1980, "b" * 520]
