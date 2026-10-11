"""A new draft and the builder's changes to it."""

from dataclasses import replace
from typing import TYPE_CHECKING

from .model import Draft, parse_color

STYLES = frozenset(("1", "2", "3", "4"))  # the color buttons' indexes: Discord's button styles

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .texts import Texts


def defaults(texts: Texts) -> Draft:
    """A new draft, its texts in the administrator's language from ``text.yaml``.

    The color is cyan, the style green, with no staff roles, in the panel channel's category.
    """
    return Draft(
        reason_title=texts.get("defaults.reason-title"),
        author=texts.get("defaults.author"),
        author_icon_url=texts.get("defaults.author-icon-url"),
        title=texts.get("defaults.title"),
        description=texts.get("defaults.description"),
        button_text=texts.get("defaults.button-text"),
        button_emoji=texts.get("defaults.button-emoji"),
    )


def submit(draft: Draft, sub_action: str, values: Mapping[str, str]) -> Draft | str:
    """The draft that the submitted modal ``sub_action`` makes of ``draft``, or the error key.

    ``values`` are the modal's inputs by ID, empty when not filled in. Empty texts unset the author,
    its icon, the title and the description; an empty reason title is ignored. The zh-TW button
    modal in some operators' files says ``modify-btn-content``, which counts as ``modify-btn-text``.
    Other modals (the preview's) change nothing.
    """
    match sub_action:
        case "modify-author":
            return replace(
                draft, author=values.get("author", ""), author_icon_url=values.get("image", "")
            )
        case "modify-content":
            return replace(draft, title=values.get("title", ""), description=values.get("desc", ""))
        case "modify-reason":
            reason = values.get("reason", "")
            return replace(draft, reason_title=reason) if reason else draft
        case "modify-embed-color":
            return _color(draft, values.get("color", ""))
        case "modify-btn-text" | "modify-btn-content":
            return _button(draft, values.get("btn-text", ""), values.get("btn-emoji", ""))
        case _:
            return draft


def _color(draft: Draft, text: str) -> Draft | str:
    """The draft with the color ``text``, or the error key."""
    color = parse_color(text)
    return "error.invalid-color" if color is None else replace(draft, color=color)


def _button(draft: Draft, text: str, emoji: str) -> Draft | str:
    """The draft with the button's label and emoji, or the error key when both are empty.

    The emoji is kept as typed: Discord refuses what is no emoji when the builder shows it.
    """
    if not text and not emoji:
        return "error.button-empty"
    return replace(draft, button_text=text, button_emoji=emoji)


def select_roles(draft: Draft, values: Sequence[str]) -> Draft:
    """The draft with the selected staff roles, which replace the earlier ones."""
    return replace(draft, admin_ids=tuple(int(value) for value in values if value.isdecimal()))


def select_style(draft: Draft, index: str) -> Draft:
    """The draft with the color button's style: 1 blue, 2 gray, 3 green, 4 red; else unchanged."""
    return replace(draft, button_style=int(index)) if index in STYLES else draft
