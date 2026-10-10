"""The texts that v3 wrote in its code, from ``text.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:207-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:181-196
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xincord.core.placeholders import render
from xincord.plugins.redaction import redact

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.i18n import Lang

TEXT = "text"  # the stem of the lang file that holds them
ERROR_MAX = 200  # v3's take(200) of an error's text


@dataclass(frozen=True)
class Texts:
    """The texts of ``text.yaml`` in one locale, each falling back to the default locale."""

    lang: Lang
    locale: str

    def get(self, key: str, values: Mapping[str, str] | None = None) -> str:
        """The text ``key`` of ``text.yaml`` with its ``%tt@...%`` values, inserted as written."""
        return render(self.lang.text(f"{TEXT}.{key}", self.locale), values or {})


def readable_error(error: BaseException) -> str:
    """An error as v3 showed it to users: its text on one line, at most 200 UTF-16 code units, or
    its class name; URLs are cut to their origin, since a webhook's URL holds its token.
    """
    text = str(error).replace("\n", " ")
    return clip(redact(text), ERROR_MAX) if text else type(error).__name__


def units(text: str) -> int:
    """The length of ``text`` in UTF-16 code units, as Java's ``String.length``."""
    return len(text.encode("utf-16-le")) // 2


def clip(text: str, limit: int) -> str:
    """The longest start of ``text`` within ``limit`` UTF-16 code units, characters kept whole."""
    used = 0
    for index, char in enumerate(text):
        used += units(char)
        if used > limit:
            return text[:index]
    return text
