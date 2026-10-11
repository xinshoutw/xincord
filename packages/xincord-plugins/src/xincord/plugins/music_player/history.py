"""One guild's history of songs and their order of play."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from .audio import Track


class LoopMode(StrEnum):
    """The two playback modes, which the loop button toggles."""

    SEQUENTIAL = "sequential"
    SINGLE = "single"


@dataclass(frozen=True)
class Requester:
    """The member who added a song."""

    id: int
    name: str  # the display name in the guild
    username: str
    avatar_url: str  # the display avatar's URL


@dataclass(frozen=True)
class Entry:
    """A song of the history and the member who added it."""

    track: Track
    requester: Requester


LIMIT = 240  # songs in a history
PREVIOUS_THRESHOLD = 5000  # milliseconds after which the previous button restarts the song


@dataclass(frozen=True)
class Added:
    """What adding songs did: how many joined, how many did not fit, and the one to start."""

    added: int
    refused: int
    start: Entry | None


class History:
    """Every song of the session in order and the index of the current one.

    ``active`` says whether the current song is on the player, playing or paused; the history is
    idle once the last song ended, and an added song then starts.
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
        """The songs after the current one, which the queue lists."""
        return self.entries[self.index + 1 :] if self.active else []

    def add(self, entries: Sequence[Entry]) -> Added:
        """Add ``entries`` after the others; the first starts when the history is idle.

        Past ``limit`` songs, played ones leave first, the index following; the songs that still
        do not fit are refused and counted.
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

        The count may reach one more than the upcoming songs, the playing one included: skipping
        that many ends the list.
        """
        if count <= len(self.upcoming):
            self.index += count
            return self.entries[self.index]
        self.index, self.active = len(self.entries) - 1, False
        return None

    def previous(self, position: int) -> Entry:
        """The previous button: restart the song, or go back one before 5000 ms.

        The song restarts from ``PREVIOUS_THRESHOLD`` on, and when it is the first one.
        """
        if self.index > 0 and position < PREVIOUS_THRESHOLD:
            self.index -= 1
        return self.entries[self.index]

    def ended(self, loop: LoopMode, *, failed: bool) -> Entry | None:
        """The current song ended: the song to start next, or None when the history goes idle.

        In single-song loop a finished song plays again; a failed one is never restarted.
        """
        if loop is LoopMode.SINGLE and not failed:
            return self.entries[self.index]
        if (following := self.skip()) is None:
            self.active = False
        return following

    def shuffle(self, rng: Random) -> int:
        """Shuffle the upcoming songs; return how many, or 0 when fewer than two."""
        upcoming = self.upcoming
        if len(upcoming) < 2:  # noqa: PLR2004 - at least two songs
            return 0
        rng.shuffle(upcoming)
        self.entries[self.index + 1 :] = upcoming
        return len(upcoming)

    def stop(self) -> None:
        """Forget every song, as ``/stop`` and ``/disconnect`` do."""
        self.entries.clear()
        self.index, self.active = 0, False

    def idle(self) -> None:
        """The player dropped the current song: nothing plays, and the songs stay."""
        self.active = False
