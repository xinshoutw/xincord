"""Reading the formula into postfix tokens."""

import pytest

from xincord.plugins.calculator.calculator import FORMULA_MAX, NEGATE, CalcError, to_postfix

IDEOGRAPHIC_SPACE = chr(0x3000)
NEXT_LINE = chr(0x85)
ARABIC_DIGITS = chr(0x661) + chr(0x662)
TIMES = chr(0xD7)


def message(formula: str) -> str:
    """The message of the error that reading ``formula`` raises."""
    with pytest.raises(CalcError) as caught:
        to_postfix(formula)
    return str(caught.value)


@pytest.mark.parametrize(
    ("formula", "postfix"),
    [
        ("2 3", ["2", "3", "*"]),
        ("2(3)", ["2", "3", "*"]),
        ("(2)3", ["2", "3", "*"]),
        ("(2)(3)", ["2", "3", "*"]),
        ("8/2(2+2)", ["8", "2", "/", "2", "2", "+", "*"]),
        ("2^3(2)", ["2", "3", "^", "2", "*"]),
        ("2 .5", ["2", ".5", "*"]),
        (f"1{IDEOGRAPHIC_SPACE}2", ["1", "2", "*"]),
    ],
)
def test_implicit_multiplication(formula: str, postfix: list[str]) -> None:
    """Requirement: Formulas are read with the calculator's syntax."""
    assert to_postfix(formula) == postfix


@pytest.mark.parametrize(
    ("formula", "postfix"),
    [
        ("1+2*3", ["1", "2", "3", "*", "+"]),
        ("1-2-3", ["1", "2", "-", "3", "-"]),
        ("1/2/2", ["1", "2", "/", "2", "/"]),
        ("1 + 2 * 3 ^ 2", ["1", "2", "3", "2", "^", "*", "+"]),
        ("(1+2)^2", ["1", "2", "+", "2", "^"]),
        ("", []),
    ],
)
def test_precedence(formula: str, postfix: list[str]) -> None:
    """Requirement: Formulas are read with the calculator's syntax."""
    assert to_postfix(formula) == postfix


@pytest.mark.parametrize(
    ("formula", "postfix"),
    [
        ("2*-3", ["2", "3", NEGATE, "*"]),
        ("2--3", ["2", "3", NEGATE, "-"]),
        ("-2*3", ["2", NEGATE, "3", "*"]),
        ("-2^2", ["2", "2", "^", NEGATE]),
        ("2^-1", ["2", "1", NEGATE, "^"]),
        ("--3", ["3", NEGATE, NEGATE]),
        ("(- 3)", ["3", NEGATE]),
        ("-2(3)", ["2", NEGATE, "3", "*"]),
        ("2^-3^2", ["2", "3", "2", "^", NEGATE, "^"]),
    ],
)
def test_minus_after_an_operator(formula: str, postfix: list[str]) -> None:
    """Requirement: Formulas are read with the calculator's syntax."""
    assert to_postfix(formula) == postfix


def test_powers_group_from_the_right() -> None:
    """Requirement: Formulas are read with the calculator's syntax."""
    assert to_postfix("2^3^2") == ["2", "3", "2", "^", "^"]
    assert to_postfix("(2^3)^2") == ["2", "3", "^", "2", "^"]


@pytest.mark.parametrize(
    ("formula", "error"),
    [
        ("1e5", "Unknown character: e"),
        ("(a", "Unknown character: a"),
        ("%bot_name%", "Unknown character: %"),
        (f"3{TIMES}2", f"Unknown character: {TIMES}"),
        (f"1{NEXT_LINE}2", f"Unknown character: {NEXT_LINE}"),
        ("1)", "Unmatched bracket"),
        (")a", "Unmatched bracket"),
        ("(1", "Unmatched bracket"),
        ("1.2.3)", "Unmatched bracket"),
    ],
)
def test_reading_errors(formula: str, error: str) -> None:
    """Requirement: Formulas are read with the calculator's syntax."""
    assert message(formula) == error


def test_numbers_are_runs_of_digits() -> None:
    """Requirement: Formulas are read with the calculator's syntax."""
    assert to_postfix("1.2.3+.") == ["1.2.3", ".", "+"]
    assert to_postfix(f"{ARABIC_DIGITS}+1") == [ARABIC_DIGITS, "1", "+"]


def test_long_formulas() -> None:
    """Requirement: Formulas are read with the calculator's syntax."""
    assert message("1" * (FORMULA_MAX + 1)) == "Formula too long"
    assert to_postfix("1" * FORMULA_MAX) == ["1" * FORMULA_MAX]
