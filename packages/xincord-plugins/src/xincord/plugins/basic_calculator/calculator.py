"""The calculator: v3's formula language, evaluated exactly.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:28
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:64-206
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

# Discord's 1024-character embed field value, minus the code fence the templates put around the
# formula and the result.
FORMULA_MAX = 1018
RESULT_MAX = FORMULA_MAX
# The most digits a value keeps in its unscaled number, and the most decimal places, so that a
# formula such as 10^999999999 fails at once instead of stalling the bot.
DIGITS_MAX = 50_000
NEXT_LINE = chr(0x85)  # whitespace for Python's str.isspace(), not for Kotlin's isWhitespace()
TRAILING = "?= "  # v3's trimEnd('?', '=', ' ')
NEGATE = "neg"  # the postfix token of a minus that negates
OPERATORS = "+-*/^"
# v3's ranks, plus the negating minus between * / and ^. Only ^ groups from the right.
PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, NEGATE: 3, "^": 4}
RIGHT_ASSOCIATIVE = frozenset("^")

UNKNOWN_CHARACTER = "Unknown character: {}"
UNMATCHED_BRACKET = "Unmatched bracket"
FORMULA_TOO_LONG = "Formula too long"


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

    As in v3, an implicit ``*`` goes between a number or ``)`` and a number or ``(``. Unlike v3,
    a minus that does not follow an operand negates instead of subtracting from a synthetic
    ``0``, and ``^`` groups from the right.

    Raises:
        CalcError: The formula is too long, has an unknown character or an unmatched bracket;
            errors come in the order of their positions, as in v3.
    """
    if len(formula) > FORMULA_MAX:
        raise CalcError(FORMULA_TOO_LONG)
    output: list[str] = []
    stack: list[str] = []
    after_operand = False  # v3's prevTokenType is NUMBER or RIGHT_PAREN
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
    """Kotlin's ``Char.isDigit()`` (Unicode ``Nd``) or ``.``, as v3 read numbers."""
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
    """Compute postfix tokens exactly, as v3's stack machine did with ``BigDecimal``.

    Returns:
        The result rounded half up to 5 places, without trailing zeros.

    Raises:
        CalcError: A token is not a number, an operator lacks operands, a division is by zero, or
            a number grows too large.
    """
    raise NotImplementedError
