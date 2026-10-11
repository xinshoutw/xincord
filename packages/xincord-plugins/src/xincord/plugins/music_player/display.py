"""What the panels show: v3's identifier rule, times, progress bar, thumbnails and queue.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/util/MusicPlayerUtils.kt:21-312
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:401-407
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:637-680
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import discord

    from .audio import Track
    from .history import Entry, LoopMode


@dataclass(frozen=True)
class Look:
    """What a panel needs besides its song: the emojis by config key and the locale's words."""

    emojis: Mapping[str, str]
    live: str  # text.yaml's `live`, in the bar of a stream
    live_length: str  # text.yaml's `live-length`, a stream's length


def identifier(query: str) -> str:
    """The node's identifier for a member's query, as v3 routed it."""
    raise NotImplementedError


def format_time(milliseconds: int) -> str:
    """v3's ``mm:ss``, or ``hh:mm:ss`` from an hour on."""
    raise NotImplementedError


def length_text(track: Track, live_length: str) -> str:
    """A song's length as v3 showed it: ``live_length`` for a stream."""
    raise NotImplementedError


def progress_bar(position: int, track: Track, *, playing: bool, look: Look) -> str:
    """v3's ``song_duration``: the play or pause emoji, the times and 15 bar emojis."""
    raise NotImplementedError


def youtube_id(url: str) -> str | None:
    """The video ID in a YouTube link, by v3's three patterns."""
    raise NotImplementedError


def thumbnail(track: Track) -> str:
    """The node's artwork, YouTube's image of a YouTube link, or v3's default image."""
    raise NotImplementedError


def track_values(
    entry: Entry, *, position: int, playing: bool, loop: LoopMode, look: Look
) -> dict[str, str]:
    """v3's ``music_player@`` values of a panel showing ``entry``."""
    raise NotImplementedError


def emoji_values(emojis: Mapping[str, str]) -> dict[str, str]:
    """The four button emojis that v3's templates named by ID."""
    raise NotImplementedError


def queue_embed(entries: Sequence[Entry], *, live_length: str, more: str) -> discord.Embed:
    """v3's list of the upcoming songs, within Discord's limits; ``more`` counts those left out."""
    raise NotImplementedError
