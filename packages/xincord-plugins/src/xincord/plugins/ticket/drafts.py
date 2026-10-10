"""A new draft and the builder's changes to it, as v3's StepManager and StepData made them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:58-104
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:181-196
"""

from typing import TYPE_CHECKING

from .model import Draft

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

    ``values`` are the modal's inputs by ID, empty when not filled in.
    """
    raise NotImplementedError
