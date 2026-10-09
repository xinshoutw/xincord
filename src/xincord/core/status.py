"""The rotating bot activity.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/statuschanger/StatusChanger.kt:16-90
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from xincord.core.config import Activity


def activity(entry: Activity) -> discord.BaseActivity:
    """Convert a configured activity into discord.py's."""
    raise NotImplementedError


async def rotate(client: discord.Client, activities: Sequence[Activity]) -> None:
    """Show each activity for its ``seconds``, in a loop; set a single one once."""
    raise NotImplementedError
