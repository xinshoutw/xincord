"""Exact results, rounded as in v3.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:162-203
"""

import pytest

from xincord.plugins.calculator.calculator import (
    DIGITS_MAX,
    NEGATE,
    RESULT_MAX,
    CalcError,
    evaluate_postfix,
    to_postfix,
)

FULLWIDTH_THREE = chr(0xFF13)
ARABIC_DIGITS = chr(0x661) + chr(0x662)


def result(formula: str) -> str:
    """The result of ``formula``."""
    return evaluate_postfix(to_postfix(formula))


def error(tokens: list[str]) -> str:
    """The message of the error that computing ``tokens`` raises."""
    with pytest.raises(CalcError) as caught:
        evaluate_postfix(tokens)
    return str(caught.value)


def product(factor: str, count: int) -> list[str]:
    """The postfix tokens that multiply ``count`` copies of ``factor``."""
    return [factor] * count + ["*"] * (count - 1)


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("123456789012345678901234567890*10", "1234567890123456789012345678900"),
        ("0.1+0.2", "0.3"),
        ("1000000*1000000", "1000000000000"),
        ("10-20", "-10"),
        ("1 + (2 * (3 + 4)) / 5", "3.8"),
        ("1.50", "1.5"),
        ("000123", "123"),
        ("5.", "5"),
        (".5", "0.5"),
        ("2*-3", "-6"),
        ("--3", "3"),
        ("0*-1", "0"),
    ],
)
def test_exact_arithmetic(formula: str, expected: str) -> None:
    """Requirement: Results are exact and rounded as in v3."""
    assert result(formula) == expected


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("2/3", "0.66667"),
        ("1/3*3", "1"),
        ("100/3", "33.33333"),
        ("-100/3", "-33.33333"),
        ("0.000005", "0.00001"),
        ("0.0000049", "0"),
        ("0-0.000001", "0"),
        ("0.000005-0.00001", "-0.00001"),
        ("-1.000005", "-1.00001"),
        ("99999.999995", "100000"),
        ("499999951/100000000000000", "0.00001"),  # rounded at 10 places, then at 5
        ("1/9999999999", "0"),
        ("-0", "0"),
        ("0.0", "0"),
    ],
)
def test_rounding(formula: str, expected: str) -> None:
    """Requirement: Results are exact and rounded as in v3."""
    assert result(formula) == expected


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        (".", "Unknown Token: ."),
        ("1.2.3", "Unknown Token: 1.2.3"),
        ("1..2", "Unknown Token: 1..2"),
        (f"{FULLWIDTH_THREE}+1", f"Unknown Token: {FULLWIDTH_THREE}"),
        (f"{ARABIC_DIGITS}+1", f"Unknown Token: {ARABIC_DIGITS}"),
        ("+3", "Illegal formula"),
        ("()", "Illegal formula"),
        ("", "Illegal formula"),
        ("-", "Illegal formula"),
        ("3-", "Illegal formula"),
        ("1**2", "Illegal formula"),
        ("1-+2", "Illegal formula"),
    ],
)
def test_number_and_operand_errors(formula: str, expected: str) -> None:
    """Requirement: Results are exact and rounded as in v3."""
    assert error(to_postfix(formula)) == expected


@pytest.mark.parametrize("formula", ["1/0", "0/0", "3/(1-1)", "1/(0.5-0.5)"])
def test_division_by_zero(formula: str) -> None:
    """Requirement: Results are exact and rounded as in v3."""
    assert error(to_postfix(formula)) == "Division by zero"


def test_errors_in_evaluation_order() -> None:
    """Requirement: Results are exact and rounded as in v3."""
    assert error(to_postfix("1/0+1.2.3")) == "Division by zero"
    assert error(to_postfix("+ 1.2.3")) == "Unknown Token: 1.2.3"


def test_too_many_digits() -> None:
    """Requirement: Results are exact and rounded as in v3."""
    count = DIGITS_MAX // 1000 + 1
    assert error(product("9" * 1000, count)) == "Too many digits"
    assert error(product("0." + "0" * 999 + "1", count)) == "Too many digits"  # decimal places
    assert error(product("9" * 600, 2)) == "Too many digits"  # longer than an embed field


def test_longest_result() -> None:
    """Requirement: Results are exact and rounded as in v3."""
    nines = "9" * RESULT_MAX
    assert evaluate_postfix([nines]) == nines
    assert evaluate_postfix([nines[1:], NEGATE]) == "-" + nines[1:]
    assert evaluate_postfix([nines[6:] + ".12345"]) == nines[6:] + ".12345"
    assert error([nines, NEGATE]) == "Too many digits"
    assert error([nines[5:] + ".12345"]) == "Too many digits"
    assert error([nines, "10", "*"]) == "Too many digits"
