"""The calculator: v3's formula language, evaluated exactly.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:28
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:64-160
"""

# Discord's 1024-character embed field value, minus the code fence the templates put around the
# formula and the result.
FORMULA_MAX = 1018
NEXT_LINE = chr(0x85)  # whitespace for Python's str.isspace(), not for Kotlin's isWhitespace()
TRAILING = "?= "  # v3's trimEnd('?', '=', ' ')
NEGATE = "neg"  # the postfix token of a minus that negates


class CalcError(ValueError):
    """A formula the calculator refuses; the message is shown to the user, in English as v3's."""


def is_space(char: str) -> bool:
    """Return whether ``char`` is whitespace for Kotlin's ``Char.isWhitespace()``, as v3 read it."""
    return char.isspace() and char != NEXT_LINE


def normalize(raw: str) -> str:
    """Trim the formula as v3 did: whitespace, then trailing ``?``, ``=`` and spaces."""
    kept = [index for index, char in enumerate(raw) if not is_space(char)]
    trimmed = raw[kept[0] : kept[-1] + 1] if kept else ""
    return trimmed.rstrip(TRAILING)


def to_postfix(formula: str) -> list[str]:
    """Read ``formula`` into postfix tokens with v3's shunting-yard pass.

    Raises:
        CalcError: The formula is too long, has an unknown character or an unmatched bracket.
    """
    raise NotImplementedError
