"""The texts that v3 wrote in its code, from ``text.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:66-131
"""

from typing import TYPE_CHECKING

from xincord.core.placeholders import render

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xincord.core.i18n import Lang

TEXT = "text"  # the stem of the lang file that holds them
MESSAGE_LIMIT = 2000  # Discord's limit for a message's content, in UTF-16 code units
ELLIPSIS = "..."


def text(lang: Lang, key: str, locale: str, values: Mapping[str, str] | None = None) -> str:
    """The text ``key`` of ``text.yaml`` in ``locale``, with its ``%ncw@...%`` values as written.

    A key missing in ``locale`` falls back to the default locale, en-US: v3's English.
    """
    return render(lang.text(f"{TEXT}.{key}", locale), values or {})


def units(content: str) -> int:
    """The length of ``content`` in UTF-16 code units, as Discord and Java count it."""
    return len(content.encode("utf-16-le")) // 2


def course_list(lang: Lang, locale: str, codes: Sequence[str]) -> str:
    """The ``list`` reply with ``codes``; the last ones give way to ``...`` to fit a message."""
    shown = list(codes)
    reply = text(lang, "reply.list", locale, {"ncw@courses": ", ".join(shown)})
    while units(reply) > MESSAGE_LIMIT and shown:
        shown.pop()
        reply = text(lang, "reply.list", locale, {"ncw@courses": ", ".join([*shown, ELLIPSIS])})
    return reply
