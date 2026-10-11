"""The application's emojis by their configured names, and Unicode ones for the missing."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .config import Emojis

VS16 = "\N{VARIATION SELECTOR-16}"  # the emoji presentation of the symbols below
# What stands for an emoji that the application lacks, by config key: v3 failed every panel then.
FALLBACKS = {
    "progress_white_start": "\N{BLACK PARALLELOGRAM}",
    "progress_white_full": "\N{BLACK PARALLELOGRAM}",
    "progress_white_end": "\N{BLACK PARALLELOGRAM}",
    "progress_black": "\N{WHITE PARALLELOGRAM}",
    "progress_black_end": "\N{WHITE PARALLELOGRAM}",
    "media_play": "\N{BLACK RIGHT-POINTING TRIANGLE}" + VS16,
    "media_pause": "\N{DOUBLE VERTICAL BAR}" + VS16,
    "media_ordered": "\N{BLACK RIGHTWARDS ARROW}" + VS16,
    "media_repeat_once": (
        "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS WITH CIRCLED ONE OVERLAY}"
    ),
    "media_previous": "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}" + VS16,
    "media_pause_resume": "\N{BLACK RIGHT-POINTING TRIANGLE WITH DOUBLE VERTICAL BAR}" + VS16,
    "media_next": "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}" + VS16,
    "media_disconnect": "\N{EJECT SYMBOL}" + VS16,
}


def resolve(names: Emojis, available: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    """The emojis by config key: the application's (``available``, by name), else Unicode ones,
    and the configured names that the application lacks."""
    resolved: dict[str, str] = {}
    missing: list[str] = []
    configured: dict[str, str] = names.model_dump()
    for key, name in configured.items():
        if (mention := available.get(name)) is None:
            resolved[key] = FALLBACKS[key]
            missing.append(name)
        else:
            resolved[key] = mention
    return resolved, missing
