"""The plugin's view of the audio node: its value types and the Protocols that the cog uses.

The cog and the sessions see only these; ``node.py`` implements them with lavalink.py, and tests
give fakes.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import discord

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


class EndReason(StrEnum):
    """Why the node ended a song: Lavalink's reasons, as lavaplayer's."""

    FINISHED = "finished"
    LOAD_FAILED = "loadFailed"
    STOPPED = "stopped"
    REPLACED = "replaced"
    CLEANUP = "cleanup"

    @property
    def may_start_next(self) -> bool:
        """Whether the next song may start: after a finished or a failed song only."""
        return self in {EndReason.FINISHED, EndReason.LOAD_FAILED}


class NodeUnavailableError(Exception):
    """No Lavalink node is connected."""


class Player(Protocol):
    """One guild's player on the node."""

    @property
    def position(self) -> int:
        """The playing song's position in milliseconds, as the node last told it, estimated."""
        ...

    async def play(self, track: Track, *, number: int, volume: int) -> None:
        """Play ``track`` from its start, unpaused, at ``volume``, replacing any other song.

        The node's events about this song carry ``number``.
        """
        ...

    async def set_pause(self, paused: bool) -> None:  # noqa: FBT001 - the node's own switch
        """Pause or resume the song."""
        ...

    async def set_volume(self, volume: int) -> None:
        """Change the volume, 100 being the source's, as lavaplayer's."""
        ...

    async def stop(self) -> None:
        """Stop the song; the node ends it as stopped."""
        ...


class Listener(Protocol):
    """What the node tells the plugin about a guild: the cog's side of the link."""

    def joined(self, guild_id: int, player: Player) -> None:
        """The bot is connecting to voice in the guild, and ``player`` plays there."""
        ...

    def left(self, guild_id: int) -> None:
        """The bot left voice in the guild, or Discord disconnected it; its player is gone."""
        ...

    async def ended(self, guild_id: int, number: int, reason: EndReason) -> None:
        """The node ended the song started as ``number``."""
        ...

    async def stuck(self, guild_id: int, number: int) -> None:
        """The node reported the song started as ``number`` stuck."""
        ...


class Link(Protocol):
    """The plugin's connection to the node, from READY until the plugin unloads."""

    @property
    def available(self) -> bool:
        """Whether the node is connected."""
        ...

    async def load(self, identifier: str) -> Loaded:
        """Load ``identifier`` on the node.

        Raises:
            NodeUnavailableError: No node answers.
        """
        ...

    def voice(
        self, client: discord.Client, channel: discord.abc.Connectable
    ) -> discord.VoiceProtocol:
        """The voice protocol that ``channel.connect(cls=link.voice)`` connects with."""
        ...

    async def leave_lost(self) -> None:
        """Leave voice where discord.py lost the connection: a new gateway session (READY again)
        forgets its voice clients without telling them."""
        ...

    async def close(self) -> None:
        """Close the connection to the node."""
        ...
