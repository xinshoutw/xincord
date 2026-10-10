"""A new draft and the builder's changes to it, as v3's StepManager and StepData made them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:58-104
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:181-196
"""

from dataclasses import replace
from typing import TYPE_CHECKING

from .model import Draft, parse_color

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .texts import Texts


def defaults(texts: Texts) -> Draft:
    """v3's new ``StepData``, its texts in the administrator's language from ``text.yaml``.

    The color (cyan), the style (green), no staff roles and the panel channel's category are v3's.
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
    its icon, the title and the description (JDA refused an empty title and icon URL, and the
    builder stopped updating); an empty reason title is ignored, as in v3. v3's zh-TW button modal,
    in operators' files, says ``modify-btn-content``, which v3's handler did not know (B2). Other
    modals (the preview's) change nothing.
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

    v3 checked for missing inputs, which Discord never sends, and an empty button failed to render.
    The emoji is kept as typed: Discord refuses what is no emoji when the builder shows it.
    """
    if not text and not emoji:
        return "error.button-empty"
    return replace(draft, button_text=text, button_emoji=emoji)
