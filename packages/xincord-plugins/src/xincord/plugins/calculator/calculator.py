"""The calculator: a formula language, evaluated exactly.

``normalize`` trims the formula and ``calculate`` evaluates it in two passes, so that the error
messages keep their order: ``to_postfix`` reads it with a shunting-yard pass, and
``evaluate_postfix`` computes the postfix tokens with exact decimals.
"""

import math
import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

# Discord's 1024-character embed field value, minus the code fence the templates put around the
# formula and the result.
FORMULA_MAX = 1018
RESULT_MAX = FORMULA_MAX
# The most digits a value keeps in its unscaled number, and the most decimal places, so that a
# formula such as 10^999999999 fails at once instead of stalling the bot.
DIGITS_MAX = 50_000
DIVISION_PLACES = 10  # a quotient's places, rounded half up
RESULT_PLACES = 5  # a result's places, rounded half up
NEXT_LINE = chr(0x85)  # whitespace for Python's str.isspace(), not for the calculator
TRAILING = "?= "  # what trimming removes from the end
NEGATE = "neg"  # the postfix token of a minus that negates
OPERATORS = "+-*/^"
# The ranks, with the negating minus between * / and ^. Only ^ groups from the right.
PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, NEGATE: 3, "^": 4}
RIGHT_ASSOCIATIVE = frozenset("^")
# A number takes ASCII digits only, so other Unicode digits fail when it is computed.
NUMBER = re.compile(r"[0-9]+\.?[0-9]*|\.[0-9]+")
_RESULT_LIMIT = 10**RESULT_MAX
_LOG2_TEN = math.log2(10)

UNKNOWN_CHARACTER = "Unknown character: {}"
UNMATCHED_BRACKET = "Unmatched bracket"
FORMULA_TOO_LONG = "Formula too long"
NOT_A_NUMBER = "Unknown Token: {}"
ILLEGAL_FORMULA = "Illegal formula"
DIVISION_BY_ZERO = "Division by zero"
TOO_MANY_DIGITS = "Too many digits"
WHOLE_EXPONENT = "Exponent must be an integer"


class CalcError(ValueError):
    """A formula the calculator refuses; the message is shown to the user, in English."""


@dataclass(frozen=True, slots=True)
class BigDecimal:
    """``unscaled / 10**scale``: a decimal without a precision limit."""

    unscaled: int
    scale: int

    @classmethod
    def parse(cls, number: str) -> Self:
        """Read a number token such as ``12``, ``1.50``, ``5.`` or ``.5``."""
        whole, _, fraction = number.partition(".")
        return cls(int(whole + fraction), len(fraction))

    def __neg__(self) -> BigDecimal:
        """Return the negated value."""
        return BigDecimal(-self.unscaled, self.scale)


def is_space(char: str) -> bool:
    """Return whether ``char`` is whitespace for the calculator: Unicode's, U+0085 aside."""
    return char.isspace() and char != NEXT_LINE


def normalize(raw: str) -> str:
    """Trim the formula: whitespace, then trailing ``?``, ``=`` and spaces."""
    kept = [index for index, char in enumerate(raw) if not is_space(char)]
    trimmed = raw[kept[0] : kept[-1] + 1] if kept else ""
    return trimmed.rstrip(TRAILING)


def calculate(formula: str) -> str:
    """Return the result of a trimmed formula.

    Raises:
        CalcError: The formula cannot be calculated; the message says why.
    """
    return evaluate_postfix(to_postfix(formula))


def to_postfix(formula: str) -> list[str]:
    """Read ``formula`` into postfix tokens with a shunting-yard pass.

    An implicit ``*`` goes between a number or ``)`` and a number or ``(``, a minus that does not
    follow an operand negates, and ``^`` groups from the right.

    Raises:
        CalcError: The formula is too long, has an unknown character or an unmatched bracket;
            errors come in the order of their positions.
    """
    if len(formula) > FORMULA_MAX:
        raise CalcError(FORMULA_TOO_LONG)
    output: list[str] = []
    stack: list[str] = []
    after_operand = False  # the previous token is a number or a )
    for part in _tokens(formula):
        if part in OPERATORS:
            if part == "-" and not after_operand:
                stack.append(NEGATE)  # a prefix: nothing to pop yet
            else:
                _push(part, stack, output)
            after_operand = False
        elif part == ")":
            _close_bracket(stack, output)
            after_operand = True
        else:
            if after_operand:
                _push("*", stack, output)
            if part == "(":
                stack.append(part)
            else:
                output.append(part)
            after_operand = part != "("
    while stack:
        operator = stack.pop()
        if operator == "(":
            raise CalcError(UNMATCHED_BRACKET)
        output.append(operator)
    return output


def _is_digit(char: str) -> bool:
    """A Unicode decimal digit (``Nd``) or ``.``: what a number is read from."""
    return char.isdecimal() or char == "."


def _tokens(formula: str) -> Iterator[str]:
    """Yield the numbers, operators and brackets of ``formula``, skipping whitespace.

    Raises:
        CalcError: An unknown character, when the reading gets to it.
    """
    index = 0
    while index < len(formula):
        char = formula[index]
        end = index + 1
        if _is_digit(char):
            while end < len(formula) and _is_digit(formula[end]):
                end += 1
            yield formula[index:end]
        elif char in OPERATORS or char in "()":
            yield char
        elif not is_space(char):
            raise CalcError(UNKNOWN_CHARACTER.format(char))
        index = end


def _push(operator: str, stack: list[str], output: list[str]) -> None:
    """Push a binary operator after moving out the operators that apply first."""
    rank = PRECEDENCE[operator]
    while stack and stack[-1] != "(":
        top = PRECEDENCE[stack[-1]]
        if top < rank or (top == rank and operator in RIGHT_ASSOCIATIVE):
            break
        output.append(stack.pop())
    stack.append(operator)


def _close_bracket(stack: list[str], output: list[str]) -> None:
    """Move out the operators since the matching ``(`` and drop it."""
    while stack and stack[-1] != "(":
        output.append(stack.pop())
    if not stack:
        raise CalcError(UNMATCHED_BRACKET)
    stack.pop()


def evaluate_postfix(tokens: Sequence[str]) -> str:
    """Compute postfix tokens exactly, with a stack machine.

    Returns:
        The result rounded half up to 5 places, without trailing zeros.

    Raises:
        CalcError: A token is not a number, an operator lacks operands, a division is by zero, or
            a number grows too large.
    """
    stack: list[BigDecimal] = []
    for part in tokens:
        if NUMBER.fullmatch(part):
            stack.append(BigDecimal.parse(part))
        elif part == NEGATE and stack:
            stack.append(-stack.pop())
        elif part in BINARY and len(stack) >= 2:  # noqa: PLR2004 - two operands
            right = stack.pop()
            stack.append(_checked(BINARY[part](stack.pop(), right)))
        elif part == NEGATE or part in BINARY:
            raise CalcError(ILLEGAL_FORMULA)
        else:
            raise CalcError(NOT_A_NUMBER.format(part))
    if len(stack) != 1:
        raise CalcError(ILLEGAL_FORMULA)
    return _format(stack[0])


def _add(left: BigDecimal, right: BigDecimal) -> BigDecimal:
    scale = max(left.scale, right.scale)
    return BigDecimal(
        left.unscaled * 10 ** (scale - left.scale) + right.unscaled * 10 ** (scale - right.scale),
        scale,
    )


def _subtract(left: BigDecimal, right: BigDecimal) -> BigDecimal:
    return _add(left, -right)


def _multiply(left: BigDecimal, right: BigDecimal) -> BigDecimal:
    return BigDecimal(left.unscaled * right.unscaled, left.scale + right.scale)


def _divide(left: BigDecimal, right: BigDecimal) -> BigDecimal:
    """Divide to ten places, rounded half up; a zero divisor is an error."""
    if right.unscaled == 0:
        raise CalcError(DIVISION_BY_ZERO)
    shift = DIVISION_PLACES + right.scale - left.scale
    numerator = left.unscaled * 10 ** max(shift, 0)
    denominator = right.unscaled * 10 ** max(-shift, 0)
    return BigDecimal(_round_half_up(numerator, denominator), DIVISION_PLACES)


def _power(base: BigDecimal, exponent: BigDecimal) -> BigDecimal:
    """Raise ``base`` to a whole ``exponent``; a negative one divides 1 by the power."""
    whole, fraction = divmod(exponent.unscaled, 10**exponent.scale)
    if fraction:
        raise CalcError(WHOLE_EXPONENT)
    count = abs(whole)
    # Lower bounds of the power's decimal places and bits, so that 10^999999999 fails at once.
    if (
        count * base.scale > DIGITS_MAX
        or count * (abs(base.unscaled).bit_length() - 1) > DIGITS_MAX * _LOG2_TEN
    ):
        raise CalcError(TOO_MANY_DIGITS)
    power = _checked(BigDecimal(base.unscaled**count, base.scale * count))
    return power if whole >= 0 else _divide(BigDecimal(1, 0), power)


BINARY: dict[str, Callable[[BigDecimal, BigDecimal], BigDecimal]] = {
    "+": _add,
    "-": _subtract,
    "*": _multiply,
    "/": _divide,
    "^": _power,
}


def _round_half_up(numerator: int, denominator: int) -> int:
    """Divide and round to an integer, ties away from zero (half up)."""
    quotient, remainder = divmod(abs(numerator), abs(denominator))
    if 2 * remainder >= abs(denominator):
        quotient += 1
    return quotient if (numerator < 0) == (denominator < 0) else -quotient


def _checked(value: BigDecimal) -> BigDecimal:
    """Refuse a value with more than ``DIGITS_MAX`` digits or decimal places."""
    if value.scale > DIGITS_MAX or abs(value.unscaled) >= _digits_limit():
        raise CalcError(TOO_MANY_DIGITS)
    return value


@cache
def _digits_limit() -> int:
    """``10**DIGITS_MAX``, computed when first needed: it takes milliseconds."""
    return 10**DIGITS_MAX


def _format(value: BigDecimal) -> str:
    """Five places, rounded half up, without trailing zeros or an exponent, never ``-0``."""
    if value.scale <= RESULT_PLACES:
        units = value.unscaled * 10 ** (RESULT_PLACES - value.scale)
    else:
        units = _round_half_up(value.unscaled, 10 ** (value.scale - RESULT_PLACES))
    whole, fraction = divmod(abs(units), 10**RESULT_PLACES)
    if whole >= _RESULT_LIMIT:  # too long, and str() refuses more than 4300 digits
        raise CalcError(TOO_MANY_DIGITS)
    text = ("-" if units < 0 else "") + str(whole)
    if fraction:
        text += "." + f"{fraction:0{RESULT_PLACES}d}".rstrip("0")
    if len(text) > RESULT_MAX:
        raise CalcError(TOO_MANY_DIGITS)
    return text
