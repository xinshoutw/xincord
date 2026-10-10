"""Trimming the formula.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:28
"""

import pytest

from xincord.plugins.calculator.calculator import normalize

IDEOGRAPHIC_SPACE = chr(0x3000)
NEXT_LINE = chr(0x85)  # whitespace for Python's str.isspace(), not for Kotlin's isWhitespace()


@pytest.mark.parametrize(
    ("raw", "formula"),
    [
        ("1+1 = ?", "1+1"),
        ("1 + 1 ==", "1 + 1"),
        ("1+1=?=", "1+1"),
        ("?", ""),
        ("1+1\t=", "1+1\t"),  # only spaces go with the trailing signs
    ],
)
def test_trailing_signs(raw: str, formula: str) -> None:
    """Requirement: Formulas are trimmed as in v3."""
    assert normalize(raw) == formula


def test_whitespace() -> None:
    """Requirement: Formulas are trimmed as in v3."""
    assert normalize(f"{IDEOGRAPHIC_SPACE}1 2{IDEOGRAPHIC_SPACE}") == "1 2"
    assert normalize("\t 7 \n") == "7"
    assert normalize(f"1+1{NEXT_LINE}") == f"1+1{NEXT_LINE}"
    assert normalize(f"{NEXT_LINE}1") == f"{NEXT_LINE}1"


def test_leading_signs_stay() -> None:
    """Requirement: Formulas are trimmed as in v3."""
    assert normalize("?1+1") == "?1+1"
    assert normalize("=1+1") == "=1+1"
