"""The texts that v3 wrote in its code, in one language per message, and the embeds built from them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:621-627
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:313-371
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.i18n import Lang


def language(lang: Lang, locale: str) -> str:
    """The locale whose texts and templates serve a user or a giveaway of ``locale``."""
    raise NotImplementedError


@dataclass(frozen=True)
class Texts:
    """The texts of ``text.yaml`` in one locale."""

    lang: Lang
    locale: str

    def get(self, key: str, values: Mapping[str, str] | None = None) -> str:
        """The text ``key`` of ``text.yaml`` with its ``%ga@...%`` values."""
        raise NotImplementedError
