"""The builder's inputs: Kotlin's trim, the winner count, the thumbnail URL and clipped texts.

The accepted and refused URLs are the inventory's, verified with JDK 25's ``java.net.URI``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:70-151
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:373-379
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:116-118
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:561-563
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:629-632
"""

import pytest

from xincord.plugins.giveaway.inputs import clip, is_http_url, thumbnail, trim, winner_count

REASON = "Builder inputs are checked as in v3"
NEXT_LINE = chr(0x85)  # whitespace for Python's isspace(), not for Kotlin's isWhitespace()
IDEOGRAPHIC_SPACE = chr(0x3000)
NO_BREAK_SPACE = chr(0xA0)
FULL_WIDTH = {str(digit): chr(0xFF10 + digit) for digit in range(10)}
ARABIC_FIVE = chr(0x665)
SMILE = chr(0x1F600)  # outside the BMP: two UTF-16 code units


@pytest.mark.parametrize(
    ("text", "trimmed"),
    [
        (" Nitro ", "Nitro"),
        (f"\t\n{IDEOGRAPHIC_SPACE}Nitro{NO_BREAK_SPACE}\x1c", "Nitro"),
        (f"{NEXT_LINE}Nitro{NEXT_LINE}", f"{NEXT_LINE}Nitro{NEXT_LINE}"),
        ("  ", ""),
        ("a b", "a b"),
    ],
)
def test_trimmed_values(text: str, trimmed: str) -> None:
    """Requirement: Builder inputs are checked as in v3."""
    assert trim(text) == trimmed


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("1", 1),
        ("50", 50),
        ("+5", 5),
        ("05", 5),
        (FULL_WIDTH["5"], 5),
        (FULL_WIDTH["1"] + FULL_WIDTH["0"], 10),
        (ARABIC_FIVE, 5),
        ("0", None),
        ("51", None),
        ("-1", None),
        ("1_0", None),
        ("1e1", None),
        ("x", None),
        ("", None),
        ("+", None),
        ("5 ", None),
        ("9" * 5000, None),
    ],
)
def test_winner_counts(text: str, count: int | None) -> None:
    """Requirement: Builder inputs are checked as in v3."""
    assert winner_count(text) == count


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/a.png",
        "HTTPS://EXAMPLE.COM/a.png",
        "http://x",
        "https://user@host:8080/p?q#f",
        "https://1.2.3.4/x",
        "https://[::1]/x",
        "https://xn--fsqu00a.xn--0zwm56d/a.png",
        "https://example.com.",
        "https://example.com:/a",
        "https://example.com?q=1",
        "https://example.com/a%20b.png",
        "https://example.com/" + chr(0x8DEF) + ".png",
        "https://example.com/a?x=[1]",
        "https://1example.com/x",
        "https://123.example.com",
        "https://01.02.03.255/x",
    ],
)
def test_accepted_urls(url: str) -> None:
    """Requirement: Builder inputs are checked as in v3."""
    assert is_http_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://",
        "https:///path",
        "ftp://x.com",
        "https://exa mple.com",
        "https://" + chr(0x4F8B) + chr(0x5B50) + ".test/a.png",
        "https://host_name.com/x",
        "https://1.2.3.400/x",
        "https://[::g]/x",
        "//host/p",
        "javascript:alert(1)",
        "https:example.com",
        "https://a@b@c/",
        "https://example.com:8a/",
        "https://example.com/a b",
        "https://example.com/a|b",
        "https://example.com/%zz",
        "https://example.com/a#b#c",
        "https://-example.com/",
        "https://example.123/",
        "https://example-.com/",
        "",
    ],
)
def test_refused_urls(url: str) -> None:
    """Requirement: Builder inputs are checked as in v3."""
    assert not is_http_url(url)


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        ("https://x/y.png", "https://x/y.png"),
        ("HTTPS://EXAMPLE.COM/a.png", "https://EXAMPLE.COM/a.png"),
        ("Http://x", "http://x"),
        ("", None),
        ("ftp://x", None),
        ("x.png", None),
    ],
)
def test_thumbnail(url: str, shown: str | None) -> None:
    """Requirement: Builder inputs are checked as in v3."""
    # v3 showed only URLs starting with a lowercase http:// or https://.
    assert thumbnail(url) == shown


def test_clip() -> None:
    """Requirement: Builder inputs are checked as in v3."""
    assert clip("a" * 1024, 1024) == "a" * 1024
    assert clip("a" * 1025, 1024) == "a" * 1021 + "..."
    # Characters outside the BMP count twice, as in Java, and are never split.
    clipped = clip(SMILE * 600, 1024)
    assert clipped == SMILE * 510 + "..."
    assert clip("abcdef", 5) == "ab..."
