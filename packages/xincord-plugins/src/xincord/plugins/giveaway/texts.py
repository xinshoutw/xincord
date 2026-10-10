"""The texts that v3 wrote in its code, in one language per message, and the embeds built from them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:621-627
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:313-371
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xincord.core.placeholders import render

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.i18n import Lang

CHINESE = "zh-TW"  # v3's zh texts
ENGLISH = "en-US"  # v3's other texts
TEXT = "text"  # the stem of the lang file that holds them


def language(lang: Lang, locale: str) -> str:
    """The locale whose texts and templates serve a user or a giveaway of ``locale``.

    The plugin's own files for the locale when it has them; else, as v3's hard-coded texts chose,
    zh-TW for a ``zh`` locale and en-US for any other. v3 took the templates from the configured
    default locale instead, so one message could mix two languages.
    """
    if locale in lang.locales:
        return locale
    return CHINESE if locale.partition("-")[0].lower() == "zh" else ENGLISH


@dataclass(frozen=True)
class Texts:
    """The texts of ``text.yaml`` in one locale, each falling back to the default locale."""

    lang: Lang
    locale: str

    def get(self, key: str, values: Mapping[str, str] | None = None) -> str:
        """The text ``key`` of ``text.yaml`` with its ``%ga@...%`` values, inserted as written."""
        return render(self.lang.text(f"{TEXT}.{key}", self.locale), values or {})
