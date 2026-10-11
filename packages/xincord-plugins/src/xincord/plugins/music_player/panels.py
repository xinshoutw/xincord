"""The players' panels: each member's last panel, edited every 5 seconds and deleted after 60.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:47-54
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:150-233
"""

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord

    from .replies import Screen

type Sleep = Callable[[float], Awaitable[object]]

REFRESH = 5.0  # seconds between two edits, v3's
LIFETIME = 60.0  # seconds after the panel's last interaction before it is deleted, v3's


@dataclass
class Panel:
    """A member's panel: what it shows, its message, and the latest interaction that edits it."""

    user_id: int
    guild_id: int
    message_id: int
    screen: Screen
    interaction: discord.Interaction  # the command, then each press of its buttons
    touched: float  # when that interaction came, on the panels' clock
    task: asyncio.Task[None] | None = None


class Panels:
    """Each member's live panel (v3 kept one per user) and its refresh loop.

    ``refresh`` edits a panel with the current song and returns False once Discord refused the
    edit; ``sleep`` and ``clock`` are the loops' waits and time, which tests replace.
    """

    def __init__(self, refresh: Callable[[Panel], Awaitable[bool]]) -> None:
        """No panel yet."""
        self.refresh = refresh
        self.sleep: Sleep = asyncio.sleep
        self.clock: Callable[[], float] = time.monotonic
        self.panels: dict[int, Panel] = {}  # by member

    async def open(
        self,
        user_id: int,
        guild_id: int,
        message_id: int,
        screen: Screen,
        interaction: discord.Interaction,
    ) -> None:
        """Track a member's new panel, deleting their previous one."""
        raise NotImplementedError

    def touch(self, message_id: int, interaction: discord.Interaction) -> bool:
        """A press on the panel ``message_id``: it lives on, edited through ``interaction``."""
        raise NotImplementedError

    def forget(self, message_id: int) -> None:
        """Stop tracking the panel ``message_id``, which its press deletes."""
        raise NotImplementedError

    async def close_guild(self, guild_id: int) -> None:
        """Delete the guild's panels: its player stopped."""
        raise NotImplementedError

    async def close(self) -> None:
        """End every refresh, as the plugin unloads."""
        raise NotImplementedError
