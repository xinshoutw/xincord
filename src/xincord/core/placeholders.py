"""``%key%`` placeholders: single-pass rendering and the v3 key families."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def render(text: str, values: Mapping[str, str]) -> str:
    """Replace each ``%key%`` that has a value, in one left-to-right pass.

    Keys without a value stay as written, ``$%`` is a literal ``%``, and substituted values are
    never scanned again.
    """
    raise NotImplementedError
