"""The plugin's view of the audio node: its value types and the Protocols that the cog uses.

The cog and the sessions see only these; ``node.py`` implements them with lavalink.py, and tests
give fakes.
"""

from dataclasses import dataclass
from enum import StrEnum

STREAM_LENGTH = 2**63 - 1  # lavaplayer's length of a stream, Java's Long.MAX_VALUE


class LoadKind(StrEnum):
    """What a Lavalink load found."""

    TRACK = "track"
    PLAYLIST = "playlist"
    SEARCH = "search"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True)
class Track:
    """A song as the node described it; ``encoded`` plays it."""

    encoded: str
    title: str
    author: str
    uri: str | None
    identifier: str
    length: int  # milliseconds; STREAM_LENGTH for a stream
    seekable: bool = True
    stream: bool = False
    artwork_url: str | None = None
    source: str = "unknown"


@dataclass(frozen=True)
class Loaded:
    """The node's answer to a load: its kind, its songs, and its error's message."""

    kind: LoadKind
    tracks: tuple[Track, ...] = ()
    error: str | None = None


class NodeUnavailableError(Exception):
    """No Lavalink node is connected."""
