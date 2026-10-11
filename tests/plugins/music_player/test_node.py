"""The lavalink.py adapter against a local Lavalink v4 node.

Kotlin (v3 played through lavaplayer in the JVM; the node replaces it):
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:84-138
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:365-471
"""

import asyncio
import importlib
import logging
import socket
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import discord
import lavalink  # pyright: ignore[reportMissingTypeStubs]
import pytest

from lavalink_fakes import PASSWORD, FakeNode, running_node, track
from plugin_fakes import until
from xincord.plugins.music_player.audio import (
    STREAM_LENGTH,
    EndReason,
    LoadKind,
    NodeUnavailableError,
    Track,
)
from xincord.plugins.music_player.config import Node
from xincord.plugins.music_player.node import open_link

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xincord.plugins.music_player.audio import Player
    from xincord.plugins.music_player.node import NodeLink

BOT_ID = 99
GUILD = 10
SONG = Track(
    "QAAA1", "Song 1", "Band 1", "https://www.youtube.com/watch?v=video1", "video1", 214000
)


@dataclass
class Recorder:
    """The plugin's side of the link: records what the node tells it."""

    joined: list[tuple[int, Player]] = field(default_factory=list[tuple[int, "Player"]])
    left: list[int] = field(default_factory=list[int])
    ended: list[tuple[int, int, EndReason]] = field(
        default_factory=list[tuple[int, int, EndReason]]
    )
    stuck: list[tuple[int, int]] = field(default_factory=list[tuple[int, int]])


class Listener:
    """A ``Listener`` that records into a ``Recorder``."""

    def __init__(self, recorder: Recorder) -> None:
        self.recorder = recorder

    def joined(self, guild_id: int, player: Player) -> None:
        self.recorder.joined.append((guild_id, player))

    def left(self, guild_id: int) -> None:
        self.recorder.left.append(guild_id)

    async def ended(self, guild_id: int, number: int, reason: EndReason) -> None:
        self.recorder.ended.append((guild_id, number, reason))

    async def stuck(self, guild_id: int, number: int) -> None:
        self.recorder.stuck.append((guild_id, number))


@dataclass
class Guild:
    """A guild whose voice state changes are recorded, then wait for ``gate`` if set, or are
    refused when ``refuse`` is set."""

    id: int
    states: list[tuple[int | None, bool, bool]] = field(
        default_factory=list[tuple[int | None, bool, bool]]
    )
    refuse: bool = False
    gate: asyncio.Event | None = None

    async def change_voice_state(
        self, *, channel: Channel | None, self_mute: bool = False, self_deaf: bool = False
    ) -> None:
        if self.refuse:
            msg = "the gateway is closed"
            raise ConnectionError(msg)
        self.states.append((None if channel is None else channel.id, self_mute, self_deaf))
        if self.gate is not None:
            await self.gate.wait()


@dataclass
class Channel:
    """A voice channel of ``guild``, as discord.py's voice protocol reads it."""

    id: int
    guild: Guild

    def _get_voice_client_key(self) -> tuple[int, str]:
        return self.guild.id, "guild_id"


@dataclass
class Scene:
    """A link to the local node, the node, and what the link told the plugin."""

    node: FakeNode
    link: NodeLink
    recorder: Recorder
    client: discord.Client

    async def voice(self, channel_id: int = 20) -> discord.VoiceProtocol:
        """Connect the bot to a channel of the guild through the link's voice protocol."""
        channel = Channel(channel_id, Guild(GUILD))
        voice = self.link.voice(self.client, cast("discord.abc.Connectable", channel))
        self.client._connection._add_voice_client(GUILD, voice)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        await voice.connect(timeout=60, reconnect=True)
        return voice

    def player(self) -> Player:
        """The player that the link handed the plugin."""
        return self.recorder.joined[-1][1]


@pytest.fixture
async def scene() -> AsyncGenerator[Scene]:
    """The link connected to a local node."""
    node = FakeNode()
    recorder = Recorder()
    async with running_node(node) as port:
        link = open_link(
            BOT_ID, Node(host="127.0.0.1", port=port, password=PASSWORD), Listener(recorder)
        )
        client = discord.Client(intents=discord.Intents.none())
        try:
            await until(lambda: link.available)
            yield Scene(node, link, recorder, client)
        finally:
            await link.close()
            await client.close()


def free_port() -> int:
    """A port that nothing on this machine listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def test_load_results(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    playlist = {"info": {"name": "Mix", "selectedTrack": -1}, "pluginInfo": {}}
    scene.node.answers = {
        "ytsearch:never": {"loadType": "search", "data": [track(1), track(2)]},
        "song": {
            "loadType": "track",
            "data": track(3, artworkUrl="https://i.ytimg.com/vi/video3/hq720.jpg"),
        },
        "radio": {
            "loadType": "track",
            "data": track(4, isStream=True, length=STREAM_LENGTH, uri=None, isSeekable=False),
        },
        "list": {"loadType": "playlist", "data": {**playlist, "tracks": [track(5), track(6)]}},
        "broken": {
            "loadType": "error",
            "data": {"message": "This video is unavailable", "severity": "common", "cause": "x"},
        },
    }

    search = await scene.link.load("ytsearch:never")
    song = await scene.link.load("song")
    radio = await scene.link.load("radio")
    mix = await scene.link.load("list")
    nothing = await scene.link.load("ytsearch:nothing")
    broken = await scene.link.load("broken")

    assert search.kind is LoadKind.SEARCH
    assert [found.title for found in search.tracks] == ["Song 1", "Song 2"]
    assert song.kind is LoadKind.TRACK
    assert song.tracks == (
        Track(
            "QAAA3",
            "Song 3",
            "Band 3",
            "https://www.youtube.com/watch?v=video3",
            "video3",
            214000,
            artwork_url="https://i.ytimg.com/vi/video3/hq720.jpg",
            source="youtube",
        ),
    )
    assert radio.tracks[0].stream is True
    assert (radio.tracks[0].uri, radio.tracks[0].seekable) == (None, False)
    assert (mix.kind, len(mix.tracks)) == (LoadKind.PLAYLIST, 2)
    assert (nothing.kind, nothing.tracks) == (LoadKind.EMPTY, ())
    assert (broken.kind, broken.error) == (LoadKind.ERROR, "This video is unavailable")


async def test_no_node() -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    link = open_link(
        BOT_ID, Node(host="127.0.0.1", port=free_port(), password=PASSWORD), Listener(Recorder())
    )
    client = discord.Client(intents=discord.Intents.none())
    try:
        assert link.available is False
        with pytest.raises(NodeUnavailableError):
            await link.load("ytsearch:never")
        with pytest.raises(NodeUnavailableError):
            await link.voice(
                client, cast("discord.abc.Connectable", Channel(20, Guild(GUILD)))
            ).connect(timeout=60, reconnect=True)
    finally:
        await link.close()
        await client.close()


async def test_player_updates(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    node = scene.node
    await scene.voice()
    player = scene.player()

    await player.play(SONG, number=5, volume=40)
    await node.event("TrackStartEvent", GUILD, track=track(1))
    await node.event("TrackStuckEvent", GUILD, track=track(1), thresholdMs=10000)
    with caplog.at_level(logging.WARNING):
        await node.event(
            "TrackExceptionEvent",
            GUILD,
            track=track(1),
            exception={"message": "Something broke", "severity": "suspicious", "cause": "x"},
        )
        await node.event("WebSocketClosedEvent", GUILD, code=4006, reason="Session", byRemote=True)
        await node.event("TrackEndEvent", GUILD, track=track(1), reason="loadFailed")
        await until(lambda: len(scene.recorder.ended) == 1)
    await player.set_pause(True)
    await player.set_volume(70)
    await player.stop()

    assert [body for guild, body in node.updates if guild == str(GUILD)] == [
        {"track": {"encoded": "QAAA1"}, "volume": 40, "paused": False},
        {"paused": True},
        {"volume": 70},
        {"track": {"encoded": None}},
    ]
    assert scene.recorder.stuck == [(GUILD, 5)]
    assert scene.recorder.ended == [(GUILD, 5, EndReason.LOAD_FAILED)]
    assert "Something broke" in caplog.text
    assert "4006" in caplog.text


async def test_voice_updates(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    node = scene.node
    voice = await scene.voice()
    state = {"guild_id": str(GUILD), "user_id": str(BOT_ID), "session_id": "voice-1"}

    await voice.on_voice_state_update(cast("Any", {**state, "channel_id": "20"}))
    await voice.on_voice_server_update(
        cast("Any", {"guild_id": str(GUILD), "token": "t", "endpoint": "voice.example"})
    )
    moved = Channel(21, Guild(GUILD))
    scene.client.get_channel = lambda channel_id: moved if channel_id == 21 else None  # pyright: ignore[reportAttributeAccessIssue]
    await voice.on_voice_state_update(cast("Any", {**state, "channel_id": "21"}))
    assert voice.channel is moved
    await voice.on_voice_state_update(cast("Any", {**state, "channel_id": None}))
    await node.until(lambda: node.deleted == [str(GUILD)])

    voice_states = [body["voice"] for _, body in node.updates if "voice" in body]
    expected = {"sessionId": "voice-1", "endpoint": "voice.example", "token": "t"}
    # lavalink.py sends the channel only with a new session: a move must reach the node too.
    assert voice_states == [{**expected, "channelId": "20"}, {**expected, "channelId": "21"}]
    assert scene.recorder.left == [GUILD]
    assert scene.client.voice_clients == []
    assert len(scene.recorder.joined) == 1


async def test_disconnect_and_close(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    node = scene.node
    voice = await scene.voice()
    channel = cast("Channel", voice.channel)
    state = {"guild_id": str(GUILD), "user_id": "99", "session_id": "voice-1"}
    await voice.on_voice_state_update(cast("Any", {**state, "channel_id": "20"}))

    await voice.disconnect(force=True)
    await voice.on_voice_state_update(  # Discord's answer, after the protocol let go
        cast("Any", {**state, "channel_id": None})
    )
    await scene.link.close()
    await node.until(lambda: node.closed == 1)

    assert channel.guild.states == [(20, False, False), (None, False, False)]
    assert node.deleted == [str(GUILD)]
    assert scene.recorder.left == [GUILD]  # once
    assert scene.link.available is False


async def test_songs_that_the_plugin_did_not_start(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    node = scene.node
    voice = await scene.voice()
    await voice.on_voice_state_update(
        cast(
            "Any", {"guild_id": str(GUILD), "user_id": "99", "session_id": "v", "channel_id": "20"}
        )
    )
    player = scene.player()
    lavalink_player = cast("Any", player).player

    await node.event("TrackEndEvent", GUILD, track=track(1), reason="finished")  # nothing played
    await lavalink_player.play(lavalink.AudioTrack(track(9), 0))  # not through the plugin
    await node.event("TrackStartEvent", GUILD, track=track(9))
    await node.event("TrackStuckEvent", GUILD, track=track(9), thresholdMs=10000)
    await node.event("TrackEndEvent", GUILD, track=track(9), reason="finished")
    await node.send(
        {
            "op": "playerUpdate",
            "guildId": str(GUILD),
            "state": {"time": 0, "position": 5000, "connected": True, "ping": 0},
        }
    )
    await until(lambda: player.position >= 5000)

    assert (scene.recorder.ended, scene.recorder.stuck) == ([], [])


async def test_a_node_that_went_away() -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    node = FakeNode()
    recorder = Recorder()
    client = discord.Client(intents=discord.Intents.none())
    async with running_node(node) as port:
        link = open_link(
            BOT_ID, Node(host="127.0.0.1", port=port, password=PASSWORD), Listener(recorder)
        )
        await until(lambda: link.available)
        voice = link.voice(client, cast("discord.abc.Connectable", Channel(20, Guild(GUILD))))
        await voice.on_voice_state_update(  # before the player exists: lavalink.py ignores it
            cast("Any", {"guild_id": str(GUILD), "user_id": "99", "channel_id": "20"})
        )
        await voice.connect(timeout=60, reconnect=True)
    player = recorder.joined[-1][1]
    try:
        for call in (
            player.play(SONG, number=1, volume=40),
            player.set_pause(True),
            player.set_volume(70),
            player.stop(),
        ):
            with pytest.raises(NodeUnavailableError):
                await call
    finally:
        await link.close()
        await client.close()


async def test_close_leaves_voice(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    node = scene.node
    voice = await scene.voice()
    channel = cast("Channel", voice.channel)
    unconnected = scene.link.voice(
        scene.client, cast("discord.abc.Connectable", Channel(30, Guild(11)))
    )
    await unconnected.on_voice_state_update(  # never connected: nothing to release
        cast("Any", {"guild_id": "11", "user_id": "99", "channel_id": None})
    )

    await scene.link.close()
    await node.until(lambda: node.closed == 1)

    assert channel.guild.states == [(20, False, False), (None, False, False)]
    assert node.deleted == [str(GUILD)]
    assert scene.recorder.left == [GUILD]


async def test_a_refused_connection(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    guild = Guild(GUILD, refuse=True)  # the gateway refuses the voice state
    voice = scene.link.voice(scene.client, cast("discord.abc.Connectable", Channel(20, guild)))
    scene.client._connection._add_voice_client(GUILD, voice)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(ConnectionError, match="the gateway is closed"):
        await voice.connect(timeout=60, reconnect=True)
    guild.refuse = False  # the link's close at the end of the test may leave voice

    assert scene.client.voice_clients == []  # discord.py forgets the protocol
    assert scene.link.voices == {}
    assert scene.recorder.left == [GUILD]  # the plugin forgets the player it got


async def test_close_when_a_leave_is_refused(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    refusing, other = Guild(GUILD), Guild(11)
    for guild in (refusing, other):
        voice = scene.link.voice(scene.client, cast("discord.abc.Connectable", Channel(20, guild)))
        scene.client._connection._add_voice_client(guild.id, voice)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        await voice.connect(timeout=60, reconnect=True)
    refusing.refuse = True

    try:
        with caplog.at_level(logging.WARNING):
            await scene.link.close()
        await scene.node.until(lambda: scene.node.closed == 1)
    finally:
        await scene.link.client.close()  # closed already once the link closes whatever happens

    assert other.states[-1] == (None, False, False)  # the other guild still leaves
    assert sorted(scene.recorder.left) == [GUILD, 11]
    assert scene.link.voices == {}
    assert "the gateway is closed" in caplog.text


async def test_a_new_connection_while_the_node_deletes(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    node = scene.node
    first = await scene.voice()
    state = {"guild_id": str(GUILD), "user_id": str(BOT_ID), "session_id": "voice-1"}
    await first.on_voice_state_update(cast("Any", {**state, "channel_id": "20"}))
    node.hold = asyncio.Event()  # the node is slow to delete the player
    leaving = asyncio.create_task(
        first.on_voice_state_update(cast("Any", {**state, "channel_id": None}))
    )
    await node.until(lambda: node.deleted == [str(GUILD)])

    second = await scene.voice()  # a member's /play connects again meanwhile
    heard = list(scene.recorder.left)
    node.hold.set()
    await leaving

    assert heard == [GUILD]  # the plugin heard of the leave before the new connection came
    assert scene.recorder.left == [GUILD]
    assert scene.link.voices == {GUILD: second}
    assert scene.client.voice_clients == [second]


async def test_a_late_leave_of_the_previous_connection(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    state = {"guild_id": str(GUILD), "user_id": str(BOT_ID)}
    first = await scene.voice()
    await first.on_voice_state_update(
        cast("Any", {**state, "session_id": "voice-1", "channel_id": "20"})
    )
    await first.disconnect(force=True)  # /disconnect
    second = await scene.voice()  # another member's /play, before Discord answered the leave

    # discord.py hands Discord's answer to the leave to the guild's protocol: the new one.
    await second.on_voice_state_update(
        cast("Any", {**state, "session_id": "voice-1", "channel_id": None})
    )
    await second.on_voice_state_update(
        cast("Any", {**state, "session_id": "voice-2", "channel_id": "20"})
    )

    assert scene.recorder.left == [GUILD]  # the first connection's, once
    assert scene.link.voices == {GUILD: second}
    assert scene.client.voice_clients == [second]
    assert scene.node.deleted == [str(GUILD)]


async def test_connections_that_a_new_session_dropped(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    dropped = await scene.voice()
    channel = cast("Channel", dropped.channel)
    kept = scene.link.voice(scene.client, cast("discord.abc.Connectable", Channel(30, Guild(11))))
    scene.client._connection._add_voice_client(11, kept)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    await kept.connect(timeout=60, reconnect=True)
    # READY again: discord.py forgot the connection; guild 11's came after it.
    scene.client._connection._remove_voice_client(GUILD)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    await scene.link.leave_lost()

    assert channel.guild.states[-1] == (None, False, False)  # the bot leaves the channel
    assert scene.node.deleted == [str(GUILD)]
    assert scene.recorder.left == [GUILD]
    assert scene.link.voices == {11: kept}
    assert scene.client.voice_clients == [kept]


async def test_a_node_that_does_not_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    module = importlib.import_module("xincord.plugins.music_player.node")
    monkeypatch.setattr(module, "REQUEST_TIMEOUT", 0.2)  # seconds; 15 in the plugin
    hold = asyncio.Event()
    node = FakeNode(hold=hold)  # the node takes the request and never answers
    async with running_node(node) as port:
        link = open_link(
            BOT_ID, Node(host="127.0.0.1", port=port, password=PASSWORD), Listener(Recorder())
        )
        try:
            await until(lambda: link.available)
            with pytest.raises(NodeUnavailableError):
                await link.load("ytsearch:never gonna")
            assert link.available  # the WebSocket stays
        finally:
            hold.set()
            await link.close()


async def test_a_connection_while_a_lost_one_leaves(scene: Scene) -> None:
    """Requirement: Songs load and play through a Lavalink node."""
    lost = await scene.voice()
    guild = cast("Channel", lost.channel).guild
    scene.client._connection._remove_voice_client(GUILD)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    guild.gate = asyncio.Event()  # the gateway is slow to take the leave
    leaving = asyncio.create_task(scene.link.leave_lost())
    await until(lambda: guild.states[-1][0] is None)

    new = await scene.voice()  # a member's /play meanwhile
    guild.gate.set()
    await leaving

    assert scene.link.voices == {GUILD: new}
    assert scene.client.voice_clients == [new]
    assert scene.recorder.left == []  # the plugin keeps the new connection's player
    assert scene.node.deleted == []
