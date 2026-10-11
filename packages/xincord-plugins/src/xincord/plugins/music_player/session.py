"""One guild's music: its history on the guild's player, the loop mode and the volume."""

import asyncio
import logging
from typing import TYPE_CHECKING

from .audio import EndReason
from .history import History, LoopMode

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from random import Random

    from .audio import Player
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

    def current(self) -> Entry:
        """The current song, which a panel shows; callers check that one plays.

        Raises:
            LookupError: The history is empty.
        """
        if (entry := self.history.current) is None:
            msg = f"guild {self.guild_id} has no song"
            raise LookupError(msg)
        return entry

    def position(self) -> int:
        """The playing song's position in milliseconds, 0 when nothing plays."""
        return self.player.position if self.player is not None and self.playing else 0

    def attach(self, player: Player) -> None:
        """The bot connected: songs play on ``player``."""
        self.player = player
        self.changed(self)

    def detach(self) -> None:
        """The bot left voice: forget the songs, as v3's ``/disconnect``.

        The volume and the loop mode stay, as v3 kept them per guild; the node's later events about
        the songs are stale.
        """
        self.player = None
        self.history.stop()
        self.paused = False
        self.number += 1
        self.changed(self)

    async def enqueue(self, entries: Sequence[Entry]) -> Added | None:
        """Add songs; the first starts when nothing plays.

        None, adding nothing, while the bot is not in voice: it may leave while the songs load or
        wait for the player.
        """
        async with self.lock:
            if (player := self.player) is None:
                return None
            added = self.history.add(entries)
            if added.start is not None:
                await self._start(player, added.start)
            return added

    async def pause(self) -> bool:
        """Pause the playing song; False when nothing plays or it is paused."""
        async with self.lock:
            if self.player is None or not self.playing or self.paused:
                return False
            await self.player.set_pause(True)
            self.paused = True
            return True

    async def resume(self) -> bool:
        """Resume the paused song; False when nothing plays or it is not paused."""
        async with self.lock:
            if self.player is None or not self.playing or not self.paused:
                return False
            await self.player.set_pause(False)
            self.paused = False
            return True

    async def toggle_pause(self) -> None:
        """v3's pause-resume button: pause the playing song, or resume the paused one.

        The lock orders the choice too, so that two quick presses pause, then resume.
        """
        async with self.lock:
            if self.player is None or not self.playing:
                return
            paused = not self.paused
            await self.player.set_pause(paused)
            self.paused = paused

    async def stop(self) -> None:
        """Forget every song and stop the player, unpaused (v3 kept the pause)."""
        async with self.lock:
            self.history.stop()
            await self._halt()

    async def skip(self) -> Entry | None:
        """Play the next song, or None at the last one."""
        async with self.lock:
            if (
                (player := self.player) is None
                or not self.playing
                or (entry := self.history.skip()) is None
            ):
                return None
            await self._start(player, entry)
            return entry

    async def skip_many(self, count: int) -> Entry | None:
        """Skip ``count`` songs: the song reached, or None when the list ended."""
        async with self.lock:
            if (player := self.player) is None or not self.playing:
                return None
            if (entry := self.history.skip_many(count)) is None:
                await self._halt()
                return None
            await self._start(player, entry)
            return entry

    async def previous(self) -> Entry | None:
        """v3's previous button: restart the song, or play the previous one before 5000 ms.

        None when nothing plays, which may change while the call waits for the player.
        """
        async with self.lock:
            if (player := self.player) is None or not self.playing:
                return None
            entry = self.history.previous(self.position())
            await self._start(player, entry)
            return entry

    def toggle_loop(self) -> LoopMode:
        """Toggle sequential and single-song loop, as v3's loop button."""
        single = self.loop is LoopMode.SEQUENTIAL
        self.loop = LoopMode.SINGLE if single else LoopMode.SEQUENTIAL
        return self.loop

    def shuffle(self, rng: Random) -> int:
        """Shuffle the upcoming songs; return how many, 0 when fewer than two."""
        return self.history.shuffle(rng)

    async def set_volume(self, volume: int) -> int:
        """Set the guild's volume, on the player too when connected; return the previous one."""
        async with self.lock:
            before, self.volume = self.volume, volume
            if self.player is not None:
                await self.player.set_volume(volume)
            return before

    async def ended(self, number: int, reason: EndReason) -> None:
        """The node ended the song started as ``number``.

        A finished song is followed as the loop mode says; a failed one by the next song, never
        restarted (v3 looped it forever); a song the node dropped leaves the player idle. Other
        reasons, and events about other songs, change nothing.
        """
        async with self.lock:
            if number != self.number or not self.playing:
                return
            if reason is EndReason.CLEANUP:
                self.history.idle()
                self.paused = False
                self.changed(self)
                return
            if reason.may_start_next:
                failed = reason is EndReason.LOAD_FAILED
                if failed:
                    self._warn("failed to load")
                await self._follow(self.history.ended(self.loop, failed=failed))

    async def stuck(self, number: int) -> None:
        """The node reported the song started as ``number`` stuck: the next song plays.

        v3 left a stuck song playing silence until a member skipped it.
        """
        async with self.lock:
            if number != self.number or not self.playing:
                return
            self._warn("got stuck")
            await self._follow(self.history.ended(self.loop, failed=True))

    async def _follow(self, entry: Entry | None) -> None:
        """Start ``entry``, or stop the player when the history went idle; a song played, so
        the bot is in voice."""
        if entry is None or (player := self.player) is None:
            await self._halt()
        else:
            await self._start(player, entry)

    async def _start(self, player: Player, entry: Entry) -> None:
        """Play ``entry`` on ``player`` as a new number, unpaused at the guild's volume; when the
        node refuses, the history goes idle."""
        self.number += 1
        self.paused = False
        try:
            await player.play(entry.track, number=self.number, volume=self.volume)
        except BaseException:
            self.history.idle()
            raise
        finally:
            self.changed(self)

    async def _halt(self) -> None:
        """Stop the player's song, if any, as a new number; nothing plays."""
        self.number += 1
        self.paused = False
        try:
            if self.player is not None:
                await self.player.stop()
        finally:
            self.changed(self)

    def _warn(self, what: str) -> None:
        entry = self.history.current
        title = entry.track.title if entry is not None else "?"
        logger.warning("MusicPlayer: guild %d: %r %s and was skipped", self.guild_id, title, what)
