"""Fakes of MusicPlayer's audio Protocols: a guild's player on the node.

``lavalink_fakes`` stands for the node itself, for the tests of the lavalink.py adapter.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xincord.plugins.music_player.audio import Track

type Call = tuple[str, object]  # a player method and what it got


@dataclass
class FakePlayer:
    """One guild's player on the node: records each call; ``play`` raises ``error`` if set."""

    calls: list[Call] = field(default_factory=list[Call])
    position: int = 0
    error: Exception | None = None

    async def play(self, track: Track, *, number: int, volume: int) -> None:
        """Record the song's title, its start number and the volume."""
        if self.error is not None:
            raise self.error
        self.calls.append(("play", (track.title, number, volume)))

    async def set_pause(self, paused: bool) -> None:  # noqa: FBT001 - as the Protocol's
        """Record the pause."""
        self.calls.append(("pause", paused))

    async def set_volume(self, volume: int) -> None:
        """Record the volume."""
        self.calls.append(("volume", volume))

    async def stop(self) -> None:
        """Record the stop."""
        self.calls.append(("stop", None))

    def played(self) -> list[object]:
        """What each ``play`` got, in order."""
        return [value for name, value in self.calls if name == "play"]
