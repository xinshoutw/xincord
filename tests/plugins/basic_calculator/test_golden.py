"""v3's golden formulas, with an independent evaluator for the answers that xincord changes.

`golden.jsonl` (3000 random formulas) and `edge-cases.jsonl` (155 picked ones) are copies of
`docs/porting/analysis/inventory/fixtures/BasicCalculator-*.jsonl`, recorded by running v3's
evaluator. A record holds the raw input, v3's trimmed formula, and v3's result, the message of its
IllegalArgumentException, or an ArithmeticException, which v3 never answered.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:27-61
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:64-206
"""

import ast
import json
import operator
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from xincord.plugins.basic_calculator.calculator import CalcError, calculate, normalize

if TYPE_CHECKING:
    from collections.abc import Callable

XFAIL = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The golden formulas give v3's answers"
)
FIXTURES = Path(__file__).parents[2] / "fixtures" / "plugins" / "basic_calculator"
NEXT_LINE = chr(0x85)  # not whitespace for Kotlin
NUMBER = re.compile(r"[0-9]+\.?[0-9]*|\.[0-9]+")
# The independent evaluator leaves the size limits to the plugin's own tests.
SIZE_LIMITED: dict[str, str] = dict.fromkeys(
    ("2^4294967297", "2^4294967296", "2^2147483648"), "Too many digits"
)
EXPONENT_MAX = 10_000  # larger exponents are left to the size limits
DIVISION_BY_ZERO = "Division by zero"
WHOLE_EXPONENT = "Exponent must be an integer"


@dataclass(frozen=True)
class Record:
    """One formula of v3's golden files."""

    raw: str
    formula: str
    answer: str | None  # the result or the error message; None when v3 did not reply


def load(name: str) -> list[Record]:
    """Read a JSONL file of v3's answers."""
    records: list[Record] = []
    # Not splitlines(): it also splits at the U+0085 that an edge case holds.
    for line in (FIXTURES / name).read_text(encoding="utf-8").split("\n"):
        if not line:
            continue
        data = json.loads(line)
        if data["ok"]:
            answer = data["result"]
        elif data["exception"] == "IllegalArgumentException":
            answer = data["message"]
        else:
            answer = None
        records.append(Record(data["input"], data["formula"], answer))
    return records


RECORDS = load("golden.jsonl") + load("edge-cases.jsonl")


def answer(formula: str) -> str:
    """The plugin's answer: the result, or the error message."""
    try:
        return calculate(formula)
    except CalcError as error:
        return str(error)


def changed_by_a_fix(record: Record) -> bool:
    """Whether a v3 defect fixed in xincord may change the record's answer.

    The fixes: a minus after an operator negates, ``^`` groups from the right and takes whole
    exponents, and v3's ArithmeticExceptions are answered.
    """
    compact = "".join(char for char in record.formula if not is_space(char))
    return record.answer is None or "^" in compact or re.search(r"[-+*/^]-", compact) is not None


def is_space(char: str) -> bool:
    """Kotlin's whitespace."""
    return char.isspace() and char != NEXT_LINE


def is_message(reply: str | None) -> bool:
    """Whether v3 replied with an error message rather than a result or nothing."""
    return reply is not None and not NUMBER.fullmatch(reply.removeprefix("-"))


class UnreadableError(Exception):
    """The independent evaluator does not read this formula."""


class RefusedError(Exception):
    """The independent evaluator refuses the formula; the message is its answer."""


def independent(formula: str) -> str | None:
    """Evaluate ``formula`` through Python's grammar, or return None when it cannot be read.

    Numbers become the names ``n0``, ``n1``, ...; implicit products get their ``*``; ``^``
    becomes ``**``. ``ast.parse`` reads the result and ``value`` walks the tree with ``Fraction``;
    nothing is executed. Python ranks a unary minus above ``*`` and below ``**`` and groups ``**``
    from the right, as the requirements do.
    """
    python = to_python(formula)
    if python is None:
        return None
    source, numbers = python
    try:
        tree = ast.parse(source, mode="eval")
        return text(half_up(value(tree.body, numbers), 5))
    except SyntaxError, UnreadableError:
        return None
    except RefusedError as refused:
        return str(refused)


def to_python(formula: str) -> tuple[str, list[Fraction | str]] | None:
    """Rewrite ``formula`` as a Python expression over named numbers.

    A run of digits and dots that is not a number stays as text and fails when it is evaluated.
    """
    parts: list[str] = []
    numbers: list[Fraction | str] = []
    for match in re.finditer(r"[0-9.]+|.", formula, re.DOTALL):
        piece = match.group()
        if piece[0] in "0123456789." or piece == "(":
            if parts and (parts[-1].startswith("n") or parts[-1] == ")"):
                parts.append("*")
            if piece == "(":
                parts.append(piece)
            else:
                parts.append(f"n{len(numbers)}")
                numbers.append(Fraction(piece) if NUMBER.fullmatch(piece) else piece)
        elif piece in "+-*/)":
            parts.append(piece)
        elif piece == "^":
            parts.append("**")
        elif not is_space(piece):
            return None
    return " ".join(parts), numbers


def value(node: ast.expr, numbers: list[Fraction | str]) -> Fraction:
    """The exact value of a parsed expression."""
    match node:
        case ast.Name(id=name):
            number = numbers[int(name[1:])]
            if isinstance(number, str):
                message = f"Unknown Token: {number}"
                raise RefusedError(message)
            return number
        case ast.UnaryOp(op=ast.USub(), operand=operand):
            return -value(operand, numbers)
        case ast.BinOp(left=left, op=op, right=right) if type(op) in OPERATIONS:
            return OPERATIONS[type(op)](value(left, numbers), value(right, numbers))
        case _:
            raise UnreadableError


def divide(left: Fraction, right: Fraction) -> Fraction:
    """A division rounded half up to 10 places."""
    if right == 0:
        raise RefusedError(DIVISION_BY_ZERO)
    return half_up(left / right, 10)


def power(base: Fraction, exponent: Fraction) -> Fraction:
    """A power with a whole exponent; a negative one divides 1 by the power."""
    if exponent.denominator != 1:
        raise RefusedError(WHOLE_EXPONENT)
    if abs(exponent) > EXPONENT_MAX:
        raise UnreadableError
    result = base ** abs(int(exponent))
    return result if exponent >= 0 else divide(Fraction(1), result)


OPERATIONS: dict[type[ast.operator], Callable[[Fraction, Fraction], Fraction]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: divide,
    ast.Pow: power,
}


def half_up(number: Fraction, places: int) -> Fraction:
    """Round to ``places`` decimal places, ties away from zero."""
    scaled = abs(number) * 10**places
    rounded = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return Fraction(rounded if number >= 0 else -rounded, 10**places)


def text(number: Fraction) -> str:
    """Plain text without trailing zeros, as v3 printed results."""
    units = int(number * 10**5)
    whole, fraction = divmod(abs(units), 10**5)
    digits = f"{whole}.{fraction:05d}".rstrip("0").rstrip(".")
    return f"-{digits}" if units < 0 else digits


@XFAIL
def test_golden_files() -> None:
    """Requirement: The golden formulas give v3's answers."""
    unexplained: list[tuple[str, str | None, str]] = []
    for record in RECORDS:
        formula = normalize(record.raw)
        got = answer(formula)
        expected = SIZE_LIMITED.get(formula) or independent(formula)
        if formula != record.formula or (
            got != record.answer and not (changed_by_a_fix(record) and got == expected)
        ):
            unexplained.append((record.raw, record.answer, got))

    assert unexplained == []


@XFAIL
def test_independent_evaluator() -> None:
    """Requirement: The golden formulas give v3's answers."""
    disagreements: list[tuple[str, str | None, str]] = []
    for record in RECORDS:
        expected = independent(record.formula)
        if expected is None:
            # Only v3's reading and number errors, and the size limits, are left unread.
            assert record.formula in SIZE_LIMITED or is_message(record.answer), record
        elif answer(record.formula) != expected:
            disagreements.append((record.formula, expected, answer(record.formula)))

    assert disagreements == []
