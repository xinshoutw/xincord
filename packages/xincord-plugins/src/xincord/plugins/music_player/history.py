"""One guild's history of songs: v3's order of play, without its defects.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/HistoryIndexManager.kt:10-252
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/TrackSchedulerCompat.kt:16-127
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from .audio import Track


class LoopMode(StrEnum):
    """v3's two playback modes, which the loop button toggles."""

    SEQUENTIAL = "sequential"
    SINGLE = "single"


@dataclass(frozen=True)
class Requester:
    """The member who added a song, as v3 kept it in lavaplayer's ``userData``."""

    id: int
    name: str  # v3's effectiveName: the display name in the guild
    username: str  # v3's user.name
    avatar_url: str  # v3's effectiveAvatarUrl


@dataclass(frozen=True)
class Entry:
    """A song of the history and the member who added it."""

    track: Track
    requester: Requester


LIMIT = 240  # v3's MAX_HISTORY_SIZE
PREVIOUS_THRESHOLD = 5000  # milliseconds after which v3's previous button restarts the song


@dataclass(frozen=True)
class Added:
    """What adding songs did: how many joined, how many did not fit, and the one to start."""

    added: int
    refused: int
    start: Entry | None


class History:
    """v3's history: every song of the session in order and the index of the current one.

    ``active`` says whether the current song is on the player, playing or paused; the history is
    idle once the last song ended, and an added song then starts (v3 only started a first song).
    """

    def __init__(self, limit: int = LIMIT) -> None:
        """Start empty, holding at most ``limit`` songs."""
        self.limit = limit
        self.entries: list[Entry] = []
        self.index = 0
        self.active = False

    @property
    def current(self) -> Entry | None:
        """The song at the index, if any: the one playing, or the last one played when idle."""
        return self.entries[self.index] if 0 <= self.index < len(self.entries) else None

    @property
    def upcoming(self) -> list[Entry]:
        """The songs after the current one, which v3's queue listed."""
        return self.entries[self.index + 1 :] if self.active else []

    def add(self, entries: Sequence[Entry]) -> Added:
        """Add ``entries`` after the others; the first starts when the history is idle.

        Past ``limit`` songs, played ones leave first, the index following; the songs that still
        do not fit are refused and counted (v3 dropped the newest silently).
        """
        played = self.index + (0 if self.active else 1) if self.entries else 0
        excess = len(self.entries) + len(entries) - self.limit
        if (drop := min(max(excess, 0), played)) > 0:
            del self.entries[:drop]
            self.index -= drop
        accepted = list(entries[: self.limit - len(self.entries)])
        first = len(self.entries)
        self.entries.extend(accepted)
        start = None
        if accepted and not self.active:
            self.index, self.active = first, True
            start = accepted[0]
        return Added(len(accepted), len(entries) - len(accepted), start)

    def skip(self) -> Entry | None:
        """Go to the next song and return it, or None at the last one (the index stays)."""
        if self.index + 1 >= len(self.entries):
            return None
        self.index += 1
        return self.entries[self.index]

    def skip_many(self, count: int) -> Entry | None:
        """Skip ``count`` songs: the song reached, or None when the list ends past the last.

        v3 allowed one more than the upcoming songs, the playing one included, then re-showed the
        last song; skipping past it ends the list, as v3's unreachable text said.
        """
        if count <= len(self.upcoming):
            self.index += count
            return self.entries[self.index]
        self.index, self.active = len(self.entries) - 1, False
        return None

    def previous(self, position: int) -> Entry:
        """v3's previous button: restart the song, or go back one before 5000 ms.

        The song restarts from ``PREVIOUS_THRESHOLD`` on, and when it is the first one.
        """
        if self.index > 0 and position < PREVIOUS_THRESHOLD:
            self.index -= 1
        return self.entries[self.index]

    def ended(self, loop: LoopMode, *, failed: bool) -> Entry | None:
        """The current song ended: the song to start next, or None when the history goes idle.

        In single-song loop a finished song plays again; a failed one is never restarted (v3
        looped it forever).
        """
        if loop is LoopMode.SINGLE and not failed:
            return self.entries[self.index]
        if (following := self.skip()) is None:
            self.active = False
        return following

    def shuffle(self, rng: Random) -> int:
        """Shuffle the upcoming songs; return how many, or 0 when fewer than two."""
        upcoming = self.upcoming
        if len(upcoming) < 2:  # noqa: PLR2004 - v3's "at least two songs"
            return 0
        rng.shuffle(upcoming)
        self.entries[self.index + 1 :] = upcoming
        return len(upcoming)

    def stop(self) -> None:
        """Forget every song, as v3's ``/stop`` and ``/disconnect`` did."""
        self.entries.clear()
        self.index, self.active = 0, False

    def idle(self) -> None:
        """The player dropped the current song: nothing plays, and the songs stay."""
        self.active = False
