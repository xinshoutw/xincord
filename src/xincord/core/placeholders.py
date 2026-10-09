"""``%key%`` placeholders: single-pass rendering and the v3 key families."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def render(text: str, values: Mapping[str, str]) -> str:
    """Replace each ``%key%`` that has a value, in one left-to-right pass.

    Keys without a value stay as written, ``$%`` is a literal ``%``, and substituted values are
    never scanned again.
    """
    out: list[str] = []
    index = 0
    while (start := text.find("%", index)) != -1:
        if start > index and text[start - 1] == "$":
            out += (text[index : start - 1], "%")
            index = start + 1
            continue
        end = text.find("%", start + 1)
        if end == -1:
            break
        out.append(text[index:start])
        key = text[start + 1 : end]
        if key in values:
            out.append(values[key])
            index = end + 1
        else:
            # The closing % may open the next placeholder, as in commons-text.
            out.append(text[start:end])
            index = end
    out.append(text[index:])
    return "".join(out)
