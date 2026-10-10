"""A listen channel's settings: which voice channels it detects, and how the menu lists them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/ChannelData.kt:8-77
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True)
class Setting:
    """v3's ``ChannelData``: the mode and the lists of one listen channel.

    A listen channel without settings is in the allow mode with empty lists, as v3's default. The
    lists keep their order and hold each channel or category ID once (v3's ``LinkedHashSet``).
    """

    allow_mode: bool = True
    allow: tuple[int, ...] = ()
    block: tuple[int, ...] = ()


def detects(setting: Setting, channel_id: int, category_id: int | None) -> bool:
    """Whether ``setting`` detects the voice channel ``channel_id`` of category ``category_id``.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError


def targets(
    settings: Mapping[int, Setting], channels: Iterable[tuple[int, int | None]]
) -> list[int]:
    """The listen channels whose settings detect one of ``channels`` (ID and category ID pairs).

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError
