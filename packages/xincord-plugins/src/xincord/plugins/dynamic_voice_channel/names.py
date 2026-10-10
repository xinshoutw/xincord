"""The names of the rooms, from the binding's format 1.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/DynamicVoiceChannel.kt:117-123
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:44-58
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.placeholders import MemberLike, UserLike

SEPARATOR = " - "  # %dvc@custom_name% is the display name up to the first one
NAME_MAX = 100  # Discord's longest channel name, which JDA counted in UTF-16 code units


def custom_name(display_name: str) -> str:
    """v3's ``%dvc@custom_name%``: the display name up to its first `` - ``."""
    raise NotImplementedError


def room_values(member: MemberLike, bot: UserLike) -> dict[str, str]:
    """The values of format 1: v3's ``Placeholder.get(member)`` and ``dvc@custom_name``."""
    raise NotImplementedError


def room_name(template: str, values: Mapping[str, str]) -> str | None:
    """Render ``template`` into a channel name, or None if it is blank or too long."""
    raise NotImplementedError
