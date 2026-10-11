"""The players' panels: each member's last panel, edited every 5 seconds and deleted after 60.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:47-54
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:150-233
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import discord

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .replies import Screen

logger = logging.getLogger(__name__)

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
        """Track a member's new panel, deleting their previous one, as v3 kept one per user."""
        if (previous := self.panels.pop(user_id, None)) is not None:
            _stop(previous)
            await _delete(previous)
        panel = Panel(user_id, guild_id, message_id, screen, interaction, self.clock())
        self.panels[user_id] = panel
        panel.task = asyncio.create_task(self._run(panel), name="MusicPlayer panel")
        panel.task.add_done_callback(_ended)

    def touch(self, message_id: int, interaction: discord.Interaction) -> bool:
        """A press on the panel ``message_id``: it lives on, edited through ``interaction``.

        The press restarts the 60 seconds and renews the 15-minute token that edits the panel;
        v3 meant to, but its key never matched (bug B4). False when no such panel is tracked.
        """
        for panel in self.panels.values():
            if panel.message_id == message_id:
                panel.interaction, panel.touched = interaction, self.clock()
                return True
        return False

    def forget(self, message_id: int) -> None:
        """Stop tracking the panel ``message_id``, which its press deletes."""
        for panel in list(self.panels.values()):
            if panel.message_id == message_id:
                self._drop(panel)
                _stop(panel)

    async def close_guild(self, guild_id: int) -> None:
        """Delete the guild's panels and end their refreshes: its player stopped."""
        closing = [panel for panel in self.panels.values() if panel.guild_id == guild_id]
        for panel in closing:
            self._drop(panel)
            _stop(panel)
        await asyncio.gather(*(_delete(panel) for panel in closing))

    async def close(self) -> None:
        """End every refresh and wait for them, as the plugin unloads."""
        tasks = [cast("asyncio.Task[None]", panel.task) for panel in self.panels.values()]
        self.panels.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, panel: Panel) -> None:
        """Every 5 seconds: delete the panel 60 seconds after its last interaction, else edit it.

        v3 scheduled a task per panel that it never cancelled (bug B5); this one ends with the
        panel: at its expiry, its replacement, its guild's stop, a refused edit or the unload.
        """
        try:
            while True:
                await self.sleep(REFRESH)
                if self.clock() - panel.touched >= LIFETIME:
                    self._drop(panel)
                    await _delete(panel)
                    return
                if not await self.refresh(panel):
                    return
        finally:
            self._drop(panel)

    def _drop(self, panel: Panel) -> None:
        """Forget ``panel`` if it is still its member's panel."""
        if self.panels.get(panel.user_id) is panel:
            del self.panels[panel.user_id]


def _stop(panel: Panel) -> None:
    """End the refresh of ``panel``, which ``open`` started."""
    cast("asyncio.Task[None]", panel.task).cancel()


async def _delete(panel: Panel) -> None:
    """Delete the panel's message; one that the member dismissed, or whose token expired, is
    gone already."""
    try:
        await panel.interaction.delete_original_response()
    except discord.HTTPException as error:
        logger.debug("MusicPlayer: panel %d was not deleted: %s", panel.message_id, error)


def _ended(task: asyncio.Task[None]) -> None:
    """Log the error that ended a refresh: nothing awaits it."""
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error("MusicPlayer: a panel stopped refreshing", exc_info=error)
