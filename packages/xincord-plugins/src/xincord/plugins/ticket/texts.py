"""The texts that v3 wrote in its code, from ``text.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:207-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:181-196
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xincord.core.placeholders import render

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.i18n import Lang

TEXT = "text"  # the stem of the lang file that holds them


@dataclass(frozen=True)
class Texts:
    """The texts of ``text.yaml`` in one locale, each falling back to the default locale."""

    lang: Lang
    locale: str

    def get(self, key: str, values: Mapping[str, str] | None = None) -> str:
        """The text ``key`` of ``text.yaml`` with its ``%tt@...%`` values, inserted as written."""
        return render(self.lang.text(f"{TEXT}.{key}", self.locale), values or {})
