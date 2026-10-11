"""One guild's music: its history on the guild's player, the loop mode and the volume.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/GuildMusicManager.kt:21-342
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/TrackSchedulerCompat.kt:16-127
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from .history import History, LoopMode

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from random import Random

    from .audio import EndReason, Player
    from .history import Added, Entry

logger = logging.getLogger(__name__)


class Session:
    """One guild's history on its player.

    Each change runs under ``lock``, in the order the commands, the presses and the node's events
    came in. ``number`` counts the songs started: an event about another number is stale. The
    session calls ``changed`` when it starts or stops playing, or connects or disconnects, so that
    the cog can leave voice after a while idle.
    """

    def __init__(self, guild_id: int, volume: int, changed: Callable[[Session], None]) -> None:
        """Start empty and idle, at ``volume``, without a player."""
        self.guild_id = guild_id
        self.volume = volume
        self.changed = changed
        self.history = History()
        self.loop = LoopMode.SEQUENTIAL
        self.paused = False
        self.player: Player | None = None
        self.number = 0
        self.lock = asyncio.Lock()

    @property
    def playing(self) -> bool:
        """Whether a song is on the player, playing or paused."""
        return self.history.active

    def position(self) -> int:
        """The playing song's position in milliseconds, 0 when nothing plays."""
        raise NotImplementedError

    def attach(self, player: Player) -> None:
        """The bot connected: songs play on ``player``."""
        raise NotImplementedError

    def detach(self) -> None:
        """The bot left voice: forget the songs, as v3's ``/disconnect``."""
        raise NotImplementedError

    async def enqueue(self, entries: Sequence[Entry]) -> Added:
        """Add songs; the first starts when nothing plays."""
        raise NotImplementedError

    async def pause(self) -> bool:
        """Pause the playing song; False when nothing plays or it is paused."""
        raise NotImplementedError

    async def resume(self) -> bool:
        """Resume the paused song; False when nothing plays or it is not paused."""
        raise NotImplementedError

    async def stop(self) -> None:
        """Forget every song and stop the player, unpaused (v3 kept the pause)."""
        raise NotImplementedError

    async def skip(self) -> Entry | None:
        """Play the next song, or None at the last one."""
        raise NotImplementedError

    async def skip_many(self, count: int) -> Entry | None:
        """Skip ``count`` songs: the song reached, or None when the list ended."""
        raise NotImplementedError

    async def previous(self) -> Entry:
        """v3's previous button: restart the song, or play the previous one before 5000 ms."""
        raise NotImplementedError

    def toggle_loop(self) -> LoopMode:
        """Toggle sequential and single-song loop, as v3's loop button."""
        raise NotImplementedError

    def shuffle(self, rng: Random) -> int:
        """Shuffle the upcoming songs; return how many, 0 when fewer than two."""
        raise NotImplementedError

    async def set_volume(self, volume: int) -> int:
        """Set the guild's volume, on the player too when connected; return the previous one."""
        raise NotImplementedError

    async def ended(self, number: int, reason: EndReason) -> None:
        """The node ended the song started as ``number``."""
        raise NotImplementedError

    async def stuck(self, number: int) -> None:
        """The node reported the song started as ``number`` stuck."""
        raise NotImplementedError
