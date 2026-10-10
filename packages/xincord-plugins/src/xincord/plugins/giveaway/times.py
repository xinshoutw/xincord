"""End times as administrators type and see them: ``yyyy-MM-dd HH:mm`` in the configured zone.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:130-146
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import tzinfo


def parse_end_time(text: str, zone: tzinfo | None) -> int | None:
    """The epoch second of ``text`` read in ``zone`` (None: the host's), or None if invalid."""
    raise NotImplementedError


def format_end_time(epoch: int, zone: tzinfo | None) -> str:
    """``epoch`` as ``yyyy-MM-dd HH:mm`` in ``zone`` (None: the host's)."""
    raise NotImplementedError
