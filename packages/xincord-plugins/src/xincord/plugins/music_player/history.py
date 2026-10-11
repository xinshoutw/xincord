"""One guild's history of songs: v3's order of play, without its defects.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/HistoryIndexManager.kt:10-252
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/TrackSchedulerCompat.kt:16-127
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
