"""The calculator: v3's formula language, evaluated exactly.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:28
"""

NEXT_LINE = chr(0x85)  # whitespace for Python's str.isspace(), not for Kotlin's isWhitespace()
TRAILING = "?= "  # v3's trimEnd('?', '=', ' ')


def is_space(char: str) -> bool:
    """Return whether ``char`` is whitespace for Kotlin's ``Char.isWhitespace()``, as v3 read it."""
    return char.isspace() and char != NEXT_LINE


def normalize(raw: str) -> str:
    """Trim the formula as v3 did: whitespace, then trailing ``?``, ``=`` and spaces."""
    kept = [index for index, char in enumerate(raw) if not is_space(char)]
    trimmed = raw[kept[0] : kept[-1] + 1] if kept else ""
    return trimmed.rstrip(TRAILING)
