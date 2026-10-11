"""The texts that v3 wrote in its code, from ``text.yaml``."""

import traceback
from typing import TYPE_CHECKING

from xincord.core.placeholders import render

if TYPE_CHECKING:
    from xincord.core.i18n import Lang

TEXT = "text"  # the stem of the lang file that holds them
PREFIX = "music_player@"  # the placeholders' prefix, v3's


def text(lang: Lang, key: str, locale: str, **values: object) -> str:
    """The text ``key`` in ``locale`` with its ``%music_player@<name>%`` values, as written.

    A key missing in ``locale`` falls back to zh-TW, which v3 showed every member.
    """
    filled = {f"{PREFIX}{name}": str(value) for name, value in values.items()}
    return render(lang.text(f"{TEXT}.{key}", locale), filled)


def raw(lang: Lang, key: str, locale: str) -> str:
    """The text ``key`` in ``locale`` with its placeholders, for code that fills them later."""
    return lang.text(f"{TEXT}.{key}", locale)


def describe(error: BaseException) -> str:
    """The error's message, as v3 showed ``e.message``, or its type when it has none."""
    return str(error) or type(error).__name__


def format_traceback(error: BaseException) -> str:
    """The error's traceback as ``logging`` prints it, without the last newline."""
    return "".join(traceback.format_exception(error)).rstrip("\n")
