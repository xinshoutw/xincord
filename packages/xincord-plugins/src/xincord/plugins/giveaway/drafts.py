"""The builder's changes to a draft, as v3's modals and buttons made them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:70-151
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:34-59
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import tzinfo

    from .model import Draft


def submit(
    draft: Draft, sub_action: str, values: Mapping[str, str], now: int, zone: tzinfo | None
) -> Draft | str:
    """The draft that the submitted modal ``sub_action`` makes, or the key of v3's error."""
    raise NotImplementedError
