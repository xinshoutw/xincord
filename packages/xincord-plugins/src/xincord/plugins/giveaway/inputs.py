"""The builder's inputs as v3 checked them, and texts cut to Discord's limits.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:70-151
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:373-379
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:629-632
"""

import ipaddress
import re
from itertools import accumulate

NEXT_LINE = chr(0x85)
# Kotlin's Char.isWhitespace() is Python's str.isspace() without U+0085; the last whitespace
# character is U+3000.
WHITESPACE = "".join(char for char in map(chr, range(0x3001)) if char.isspace())
KOTLIN_WHITESPACE = WHITESPACE.replace(NEXT_LINE, "")

# Kotlin's toIntOrNull(): an optional sign and decimal digits of any script. More digits than an
# Int holds gave null; nine are enough for 1 to 50 and stay below Python's conversion limit.
COUNT = re.compile(r"[+-]?\d{1,9}")
WINNER_MIN, WINNER_MAX = 1, 50

# java.net.URI's grammar (RFC 2396 with RFC 2732's brackets) for a server-based authority. Java
# also takes its "other" characters, neither ASCII nor control nor space, outside the host.
UNRESERVED = r"A-Za-z0-9\-_.!~*'()"
ESCAPED = r"%[0-9A-Fa-f]{2}"
OTHER = r"[^\x00-\x9f\s]"
USER_INFO = rf"(?:[{UNRESERVED};:&=+$,]|{ESCAPED}|{OTHER})*"
HOST_NAME = (
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)*[A-Za-z](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.?"
)
IPV4 = r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}"
IPV6 = r"\[[^\[\]]*\]"
PATH_CHAR = rf"(?:[{UNRESERVED}:@&=+$,;]|{ESCAPED}|{OTHER})"
URI_CHAR = rf"(?:[{UNRESERVED};/?:@&=+$,\[\]]|{ESCAPED}|{OTHER})"
URL = re.compile(
    rf"(?i:https?)://(?:{USER_INFO}@)?(?P<host>{HOST_NAME}|{IPV4}|{IPV6})(?::[0-9]*)?"
    rf"(?:/{PATH_CHAR}*)*(?:\?{URI_CHAR}*)?(?:#{URI_CHAR}*)?"
)
ADDRESS = re.compile(IPV4)
OCTET_MAX = 255
SCHEMES = ("http", "https")

MORE = "..."  # what a clipped text ends with, as v3's clipFieldText


def trim(text: str) -> str:
    """``text`` without leading and trailing whitespace, as Kotlin's ``String.trim()``."""
    return text.strip(KOTLIN_WHITESPACE)


def winner_count(text: str) -> int | None:
    """The winner count that ``text`` holds, from 1 to 50, or None.

    v3 read it with ``toIntOrNull()``, which takes a sign and Unicode decimal digits (full-width
    too) but no ``_``, which Python's ``int`` would take.
    """
    if COUNT.fullmatch(text) is None:
        return None
    count = int(text)
    return count if WINNER_MIN <= count <= WINNER_MAX else None


def is_http_url(text: str) -> bool:
    """Whether ``text`` is an http or https URL with a host, as v3's check with Java's ``URI``.

    The scheme counts in any case; the host is a host name, an IPv4 address with parts up to 255
    or a bracketed IPv6 address. Java read any other authority as registry-based, without a host,
    and v3 refused it; characters outside the URI grammar made it throw, refused too.
    """
    match = URL.fullmatch(text)
    if match is None:
        return False
    host = match["host"]
    if host.startswith("["):
        try:
            ipaddress.IPv6Address(host[1:-1])
        except ValueError:
            return False
        return True
    if ADDRESS.fullmatch(host) is None:  # a host name, whose last label starts with a letter
        return True
    return all(int(part) <= OCTET_MAX for part in host.split("."))


def thumbnail(url: str) -> str | None:
    """The URL to show as a thumbnail, with its scheme in lower case, or None.

    v3 showed only URLs that started with a lowercase ``http://`` or ``https://``, although its
    check took any case.
    """
    scheme, separator, rest = url.partition("://")
    if separator and scheme.lower() in SCHEMES:
        return f"{scheme.lower()}://{rest}"
    return None


def units(text: str) -> int:
    """The length of ``text`` in UTF-16 code units, as Java's ``String.length``."""
    return len(text.encode("utf-16-le")) // 2


def clip(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` UTF-16 code units with ``...``, as v3's ``clipFieldText``.

    A longer text keeps the characters that fit before ``...``; v3 could split a character outside
    the BMP in two.
    """
    if units(text) <= limit:
        return text
    room = limit - units(MORE)
    # The running totals grow, so the characters that fit are the first ones.
    fitting = sum(1 for total in accumulate(map(units, text)) if total <= room)
    return text[:fitting] + MORE
