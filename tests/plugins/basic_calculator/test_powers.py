"""Powers with whole exponents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:183
"""

import time

import pytest

from xincord.plugins.basic_calculator.calculator import CalcError, evaluate_postfix, to_postfix

XFAIL = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Powers take whole exponents"
)


def result(formula: str) -> str:
    """The result of ``formula``."""
    return evaluate_postfix(to_postfix(formula))


def error(formula: str) -> str:
    """The message of the error that computing ``formula`` raises."""
    with pytest.raises(CalcError) as caught:
        result(formula)
    return str(caught.value)


@XFAIL
@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("2^64", "18446744073709551616"),
        ("0.5^2", "0.25"),
        ("1.5^2", "2.25"),
        ("0^0", "1"),
        ("0^1", "0"),
        ("2^2.0", "4"),
        ("2^(4/2)", "4"),
        ("(-2)^3", "-8"),
        ("-2^2", "-4"),
        ("2^3^2", "512"),
        ("1+2*3^2", "19"),
    ],
)
def test_whole_exponents(formula: str, expected: str) -> None:
    """Requirement: Powers take whole exponents."""
    assert result(formula) == expected


@XFAIL
@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("2^-1", "0.5"),
        ("2^(0-2)", "0.25"),
        ("3^-1", "0.33333"),
        ("(-2)^-1", "-0.5"),
        ("3^-1*300000", "99999.99999"),  # 1/3 rounded at 10 places, as 1/3^1 is
        ("10^-11", "0"),
    ],
)
def test_negative_exponents(formula: str, expected: str) -> None:
    """Requirement: Powers take whole exponents."""
    assert result(formula) == expected
    assert error("0^-1") == "Division by zero"


@XFAIL
@pytest.mark.parametrize("formula", ["2^0.5", "4^(1/2)", "4^-0.5", "0^0.5"])
def test_fractional_exponents(formula: str) -> None:
    """Requirement: Powers take whole exponents."""
    assert error(formula) == "Exponent must be an integer"


@XFAIL
@pytest.mark.parametrize(
    "formula",
    ["10^999999999", "2^4294967297", "2^4294967296", "0.1^60000", "9^99999", "(-10)^-60000"],
)
def test_huge_powers(formula: str) -> None:
    """Requirement: Powers take whole exponents."""
    started = time.perf_counter()

    assert error(formula) == "Too many digits"
    assert time.perf_counter() - started < 1  # refused before computing


@XFAIL
def test_trivial_bases() -> None:
    """Requirement: Powers take whole exponents."""
    assert result("1^4294967297") == "1"
    assert result("(-1)^4294967297") == "-1"
    assert result("0^4294967297") == "0"
