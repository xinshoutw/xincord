"""Fakes of MusicPlayer's audio Protocols: the link to the node, its players and voice.

``lavalink_fakes`` stands for the node itself, for the tests of the lavalink.py adapter.
"""

import asyncio
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING, Any

import yaml

from xincord.plugins.music_player.audio import Loaded, LoadKind, NodeUnavailableError, Track

if TYPE_CHECKING:
    from xincord.plugins.music_player.audio import Listener

type Call = tuple[str, object]  # a player method and what it got
PACKAGE = "xincord.plugins.music_player"
WAIT = 5  # seconds before a test's wait gives up


@cache
def _texts(locale: str) -> dict[str, str]:
    """The bundled ``text.yaml`` of ``locale``."""
    path = files(PACKAGE).joinpath(f"lang/{locale}/text.yaml")
    texts: dict[str, str] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return texts


def text(key: str, locale: str = "en-US", /, **values: object) -> str:
    """The bundled text ``key`` in ``locale`` with its ``%music_player@<name>%`` values."""
    found = _texts(locale)[key]
    for name, value in values.items():
        found = found.replace(f"%music_player@{name}%", str(value))
    return found


def song(number: int, **fields: Any) -> Track:  # noqa: ANN401 - Track's fields
    """Song ``number`` on YouTube, 3:34 long, with ``fields`` overriding Track's."""
    values: dict[str, Any] = {
        "encoded": f"QAAA{number}",
        "title": f"Song {number}",
        "author": f"Band {number}",
        "uri": f"https://www.youtube.com/watch?v=video{number}",
        "identifier": f"video{number}",
        "length": 214_000,
        "source": "youtube",
    }
    return Track(**(values | fields))


def loaded(kind: LoadKind, *tracks: Track, error: str | None = None) -> Loaded:
    """The node's answer of ``kind`` with ``tracks``."""
    return Loaded(kind, tracks, error)


@dataclass
class FakePlayer:
    """One guild's player on the node: records each call; ``play`` raises ``error`` if set, and
    ``set_pause`` waits for ``hold`` if set, once recorded."""

    calls: list[Call] = field(default_factory=list[Call])
    position: int = 0
    error: Exception | None = None
    hold: asyncio.Event | None = None

    async def play(self, track: Track, *, number: int, volume: int) -> None:
        """Record the song's title, its start number and the volume."""
        if self.error is not None:
            raise self.error
        self.calls.append(("play", (track.title, number, volume)))

    async def set_pause(self, paused: bool) -> None:  # noqa: FBT001 - as the Protocol's
        """Record the pause, then wait for ``hold`` if set: the node is slow to answer."""
        self.calls.append(("pause", paused))
        if self.hold is not None:
            await self.hold.wait()

    async def set_volume(self, volume: int) -> None:
        """Record the volume."""
        self.calls.append(("volume", volume))

    async def stop(self) -> None:
        """Record the stop."""
        self.calls.append(("stop", None))

    def played(self) -> list[object]:
        """What each ``play`` got, in order."""
        return [value for name, value in self.calls if name == "play"]


@dataclass
class FakeLink:
    """The link to the node: load answers by identifier, a player per connected guild.

    ``listener`` is the plugin's side, which a test or the plugin's own ``open_link`` sets. While
    ``available`` is False, loads and connections fail as the node's absence does; a load waits
    for ``gate`` when it is set.
    """

    answers: dict[str, Loaded] = field(default_factory=dict[str, Loaded])
    players: dict[int, FakePlayer] = field(default_factory=dict[int, FakePlayer])
    loads: list[str] = field(default_factory=list[str])
    connects: list[tuple[int, int]] = field(default_factory=list[tuple[int, int]])  # guild, channel
    disconnects: list[int] = field(default_factory=list[int])
    listener: Listener | None = None
    available: bool = True
    gate: asyncio.Event | None = None
    closed: bool = False
    voices: dict[int, FakeVoice] = field(default_factory=dict[int, "FakeVoice"])  # by guild

    async def load(self, identifier: str) -> Loaded:
        """Record the load, then answer it, or raise as an absent node."""
        self.loads.append(identifier)
        if self.gate is not None:
            await self.gate.wait()
        if not self.available:
            raise NodeUnavailableError
        return self.answers.get(identifier, Loaded(LoadKind.EMPTY))

    def voice(self, client: object, channel: object) -> FakeVoice:
        """The voice protocol for ``channel``."""
        del client
        return FakeVoice(self, channel)

    async def leave_lost(self) -> None:
        """Leave voice where the guild no longer has the connection as its voice client."""
        for voice in list(self.voices.values()):
            if voice.channel.guild.voice_client is not voice:
                await voice.disconnect(force=True)

    async def close(self) -> None:
        """Leave voice in every guild, as the plugin's link does, then record the close."""
        for voice in list(self.voices.values()):
            await voice.disconnect(force=True)
        self.closed = True


class FakeVoice:
    """The bot's voice connection to ``channel`` (a ``FakeVoiceChannel`` of a ``FakeGuild``)."""

    def __init__(self, link: FakeLink, channel: object) -> None:
        self.link = link
        self.channel: Any = channel

    async def connect(
        self,
        *,
        timeout: float,  # noqa: ASYNC109 - discord.py's signature
        reconnect: bool,
        self_deaf: bool = False,
        self_mute: bool = False,
    ) -> None:
        """Create the guild's player, hand it to the plugin, and become the guild's voice client."""
        del timeout, reconnect, self_deaf, self_mute
        if not self.link.available:
            raise NodeUnavailableError
        guild = self.channel.guild
        player = FakePlayer()
        self.link.players[guild.id] = player
        self.link.connects.append((guild.id, self.channel.id))
        self.link.voices[guild.id] = self
        assert self.link.listener is not None
        self.link.listener.joined(guild.id, player)
        guild.voice_client = self

    async def disconnect(self, *, force: bool) -> None:
        """Leave: the guild has no voice client, and the plugin hears that the bot left."""
        del force
        self.link.disconnects.append(self.channel.guild.id)
        self.gone()

    def gone(self) -> None:
        """Discord ended the connection (a moderator's disconnection, or after a leave)."""
        guild = self.channel.guild
        guild.voice_client = None
        self.link.players.pop(guild.id, None)
        self.link.voices.pop(guild.id, None)
        assert self.link.listener is not None
        self.link.listener.left(guild.id)


@dataclass
class Clock:
    """The plugin's waits and monotonic time: a wait lasts until the test moves the time on.

    ``advance`` moves the time and ends the waits under way; ``asleep(n)`` waits until ``n``
    waits are under way, so that a test knows that a loop finished a round.
    """

    time: float = 1000.0
    waits: list[float] = field(default_factory=list[float])  # every wait asked, in order
    _pending: list[asyncio.Future[None]] = field(default_factory=list[asyncio.Future[None]])
    _changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    def monotonic(self) -> float:
        """Stands for ``time.monotonic``."""
        return self.time

    async def sleep(self, seconds: float) -> None:
        """Stands for ``asyncio.sleep``: record the wait and wait for ``advance``."""
        future = asyncio.get_running_loop().create_future()
        async with self._changed:
            self._pending.append(future)
            self.waits.append(seconds)
            self._changed.notify_all()
        await future

    def under_way(self) -> int:
        """The waits under way."""
        return sum(1 for future in self._pending if not future.done())

    async def asleep(self, count: int) -> None:
        """Wait until ``count`` waits are under way.

        Raises:
            TimeoutError: They were not within ``WAIT`` seconds.
        """
        async with asyncio.timeout(WAIT), self._changed:
            await self._changed.wait_for(lambda: self.under_way() >= count)

    async def advance(self, seconds: float) -> None:
        """Move the time on by ``seconds`` and end the waits under way."""
        self.time += seconds
        pending, self._pending = self._pending, []
        for future in pending:
            if not future.done():
                future.set_result(None)
        await asyncio.sleep(0)  # let the woken tasks run up to their next await
