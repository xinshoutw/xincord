"""The plugin's texts outside its templates, from ``text.yaml``."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xincord.core.placeholders import render
from xincord.plugins.redaction import redact

if TYPE_CHECKING:
    from collections.abc import Mapping

    import discord

    from xincord.core.i18n import Lang

TEXT = "text"  # the stem of the lang file that holds them
ERROR_MAX = 200  # the most of an error's text that users see


@dataclass(frozen=True)
class Texts:
    """The texts of ``text.yaml`` in one locale, each falling back to the default locale."""

    lang: Lang
    locale: str

    def get(self, key: str, values: Mapping[str, str] | None = None) -> str:
        """The text ``key`` of ``text.yaml`` with its ``%tt@...%`` values, inserted as written."""
        return render(self.lang.text(f"{TEXT}.{key}", self.locale), values or {})


async def tell(interaction: discord.Interaction, text: str) -> None:
    """Answer the interaction with ``text``, ephemerally."""
    await interaction.response.send_message(text, ephemeral=True)


def readable_error(error: BaseException) -> str:
    """An error as users see it: its text on one line, at most 200 UTF-16 code units, or
    its class name; URLs are cut to their origin, since a webhook's URL holds its token.
    """
    text = str(error).replace("\n", " ")
    return clip(redact(text), ERROR_MAX) if text else type(error).__name__


def units(text: str) -> int:
    """The length of ``text`` in UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def clip(text: str, limit: int) -> str:
    """The longest start of ``text`` within ``limit`` UTF-16 code units, characters kept whole."""
    used = 0
    for index, char in enumerate(text):
        used += units(char)
        if used > limit:
            return text[:index]
    return text


def chunks(text: str, limit: int) -> list[str]:
    """``text`` in parts of at most ``limit`` UTF-16 code units each, characters kept whole."""
    parts: list[str] = []
    while units(text) > limit:
        part = clip(text, limit)
        parts.append(part)
        text = text[len(part) :]
    return [*parts, text]
