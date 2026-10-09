"""The rotating bot activity.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/statuschanger/StatusChanger.kt:16-90
"""

import asyncio
import itertools
import logging
from typing import TYPE_CHECKING

import discord

from xincord.core.config import ActivityType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xincord.core.config import Activity

logger = logging.getLogger(__name__)


def activity(entry: Activity) -> discord.BaseActivity:
    """Convert a configured activity into discord.py's."""
    match entry.type:
        case ActivityType.STREAMING:
            return discord.Streaming(name=entry.text, url=entry.url or "")
        case ActivityType.CUSTOM:
            return discord.CustomActivity(entry.text)
        case _:
            return discord.Activity(type=discord.ActivityType[entry.type.value], name=entry.text)


async def rotate(client: discord.Client, activities: Sequence[Activity]) -> None:
    """Show each activity for its ``seconds``, in a loop; set a single one once."""
    if not activities:
        return
    for entry in itertools.cycle(activities):
        try:
            await client.change_presence(activity=activity(entry))
        except Exception:
            logger.exception("Showing the activity %r failed", entry.text)
        if len(activities) == 1:
            return  # discord.py sends the stored presence again after a reconnect
        await asyncio.sleep(entry.seconds)
