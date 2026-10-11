"""The Lavalink node through lavalink.py: loads, the guilds' players, events and voice.

lavalink.py 5.11.1 sends the voice state's ``channelId`` that Lavalink 4.2 needs for DAVE. Its
``DefaultPlayer`` starts the next song of its own queue when one ends; the plugin's sessions
decide that instead, so the player class here reports the events and starts nothing.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:84-138
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/util/MusicPlayerUtils.kt:72-82
"""

import logging
from typing import TYPE_CHECKING, Any, ClassVar, cast, override

import aiohttp
import discord
import lavalink  # pyright: ignore[reportMissingTypeStubs]

from xincord.plugins.redaction import redact

from .audio import EndReason, Loaded, LoadKind, NodeUnavailableError, Track

if TYPE_CHECKING:
    from discord.types.voice import GuildVoiceState, VoiceServerUpdate

    from .audio import Listener
    from .config import Node

logger = logging.getLogger(__name__)

REGION = "default"  # lavalink.py's node regions; the plugin has one node
NAME = "lavalink"  # the node's name in lavalink.py's logs
# Seconds before a request that the node does not answer fails; lavalink.py's default is aiohttp's
# 5 minutes, which held a guild's player and a member's command that long.
REQUEST_TIMEOUT = 15.0
# What lavalink.py raises when the node does not answer: no node, a refused password, a failed or
# timed-out request.
UNAVAILABLE = (
    lavalink.ClientError,
    lavalink.AuthenticationError,
    aiohttp.ClientError,
    OSError,
    TimeoutError,
)


class NodePlayer(lavalink.DefaultPlayer):
    """lavalink.py's player without its queue: it reports the node's events to the plugin.

    ``listener`` is a class attribute: lavalink.py creates players from the class, so each link
    makes its own subclass (``open_link``).
    """

    listener: ClassVar[Listener]

    @override
    async def handle_event(self, event: lavalink.Event) -> None:
        """Report ends and stuck songs with their start numbers; log failures and closed voice.

        lavalink.py calls it in the order of the node's messages; a song that the plugin did not
        start has no number and is left out.
        """
        guild = self.guild_id
        if isinstance(event, lavalink.TrackEndEvent):
            if (number := _number(event.track)) is not None:
                await self.listener.ended(guild, number, EndReason(event.reason.value))
        elif isinstance(event, lavalink.TrackStuckEvent):
            if (number := _number(event.track)) is not None:
                await self.listener.stuck(guild, number)
        elif isinstance(event, lavalink.TrackExceptionEvent):
            logger.warning(
                "MusicPlayer: guild %d: the node failed to play %r: %s",
                guild,
                event.track.title,
                redact(str(event.message)),
            )
        elif isinstance(event, lavalink.WebSocketClosedEvent):
            logger.warning(
                "MusicPlayer: guild %d: Discord closed the node's voice connection: %d %s",
                guild,
                event.code,
                event.reason,
            )


def _number(track: lavalink.AudioTrack | None) -> int | None:
    """The start number that ``GuildPlayer.play`` gave the song, if the plugin started it."""
    extra = cast("dict[str, object]", track.extra) if track is not None else {}
    number = extra.get("number")
    return number if isinstance(number, int) else None


class GuildPlayer:
    """One guild's lavalink.py player as the plugin's ``Player``."""

    def __init__(self, player: lavalink.DefaultPlayer) -> None:
        """Wrap ``player``."""
        self.player = player

    @property
    def position(self) -> int:
        """The playing song's position, as lavalink.py estimates it from the node's updates."""
        return int(self.player.position)

    async def play(self, track: Track, *, number: int, volume: int) -> None:
        """Play ``track`` from its start, unpaused, at ``volume``; its events carry ``number``.

        Raises:
            NodeUnavailableError: The node does not answer.
        """
        song = lavalink.AudioTrack(_raw(track), 0, number=number)
        try:
            await self.player.play(song, volume=volume, pause=False)  # pyright: ignore[reportUnknownMemberType]
        except UNAVAILABLE as error:
            raise NodeUnavailableError from error

    async def set_pause(self, paused: bool) -> None:  # noqa: FBT001 - as the Protocol's
        """Pause or resume the song."""
        try:
            await self.player.set_pause(paused)
        except UNAVAILABLE as error:
            raise NodeUnavailableError from error

    async def set_volume(self, volume: int) -> None:
        """Change the volume."""
        try:
            await self.player.set_volume(volume)
        except UNAVAILABLE as error:
            raise NodeUnavailableError from error

    async def stop(self) -> None:
        """Stop the song."""
        try:
            await self.player.stop()
        except UNAVAILABLE as error:
            raise NodeUnavailableError from error


def _raw(track: Track) -> dict[str, Any]:
    """``track`` as the node's track object, which lavalink.py plays from its encoded string."""
    return {
        "encoded": track.encoded,
        "info": {
            "identifier": track.identifier,
            "isSeekable": track.seekable,
            "author": track.author,
            "length": track.length,
            "isStream": track.stream,
            "position": 0,
            "title": track.title,
            "uri": track.uri,
            "artworkUrl": track.artwork_url,
            "isrc": None,
            "sourceName": track.source,
        },
        "pluginInfo": {},
        "userData": {},
    }


def _track(song: lavalink.AudioTrack) -> Track:
    """The node's song as the plugin's ``Track``."""
    return Track(
        encoded=str(song.track),
        title=str(song.title),
        author=str(song.author),
        uri=cast("str | None", song.uri),
        identifier=str(song.identifier),
        length=int(song.duration),
        seekable=bool(song.is_seekable),
        stream=bool(song.is_stream),
        artwork_url=song.artwork_url,
        source=str(song.source_name),
    )


class NodeLink:
    """The plugin's lavalink.py client with its one node."""

    def __init__(self, client: lavalink.Client[NodePlayer], listener: Listener) -> None:
        """Keep the client and the plugin's listener."""
        self.client = client
        self.listener = listener
        self.closed = False
        self.voices: dict[int, LavalinkVoice] = {}  # the bot's connections, by guild

    @property
    def available(self) -> bool:
        """Whether the node's WebSocket is connected."""
        return not self.closed and any(node.available for node in self.client.node_manager.nodes)

    async def load(self, identifier: str) -> Loaded:
        """Load ``identifier`` on the node.

        Raises:
            NodeUnavailableError: The node does not answer.
        """
        try:
            result = await self.client.get_tracks(identifier)
        except UNAVAILABLE as error:
            raise NodeUnavailableError from error
        error = result.error.message if result.error is not None else None
        tracks = tuple(_track(song) for song in result.tracks)
        return Loaded(LoadKind(result.load_type.value), tracks, error)

    def voice(self, client: discord.Client, channel: discord.abc.Connectable) -> LavalinkVoice:
        """The voice protocol that ``channel.connect(cls=link.voice)`` connects with."""
        return LavalinkVoice(client, channel, self)

    async def leave_lost(self) -> None:
        """Leave voice where discord.py lost the connection: a new gateway session (READY again)
        forgets its voice clients without telling them."""
        for voice in list(self.voices.values()):
            if self.voices.get(voice.guild_id) is voice and voice not in voice.client.voice_clients:
                await self._leave(voice)

    async def close(self) -> None:
        """Leave voice in every guild, then close the node's connection and the client's
        session; again does nothing."""
        if self.closed:
            return
        self.closed = True
        try:
            for voice in list(self.voices.values()):
                await self._leave(voice)
        finally:
            await self.client.close()

    async def _leave(self, voice: LavalinkVoice) -> None:
        """Leave ``voice``'s channel; a refused leave is logged, and the connection is released
        all the same."""
        try:
            await voice.disconnect(force=True)
        except Exception as error:  # noqa: BLE001 - logged, and the other guilds still leave
            logger.warning(
                "MusicPlayer: could not leave voice in guild %d: %s",
                voice.guild_id,
                redact(str(error)),
            )


class LavalinkVoice(discord.VoiceProtocol):
    """The bot's voice connection in a guild, which the node makes from its voice updates."""

    def __init__(
        self, client: discord.Client, channel: discord.abc.Connectable, link: NodeLink
    ) -> None:
        """A protocol for ``channel``'s guild."""
        super().__init__(client, channel)
        self.link = link
        self.guild_id: int = cast("discord.VoiceChannel", channel).guild.id
        self.released = False
        # Discord put the bot in a channel through this connection: a voice state without a
        # channel is its end from then on, and before that the late end of an earlier connection.
        self.confirmed = False

    @override
    async def connect(
        self,
        *,
        timeout: float,
        reconnect: bool,
        self_deaf: bool = False,
        self_mute: bool = False,
    ) -> None:
        """Create the guild's player, hand it to the plugin and ask Discord to connect the bot.

        The bot is neither deafened nor muted, as in v3; Discord's voice updates follow.

        Raises:
            NodeUnavailableError: No node is connected; discord.py then forgets the protocol.
            Exception: The gateway refused the voice state; the connection is released.
        """
        del timeout, reconnect
        try:
            player = self.link.client.player_manager.create(self.guild_id)
        except lavalink.ClientError as error:
            self.cleanup()
            raise NodeUnavailableError from error
        self.link.voices[self.guild_id] = self
        self.link.listener.joined(self.guild_id, GuildPlayer(player))
        guild = cast("discord.VoiceChannel", self.channel).guild
        try:
            await guild.change_voice_state(
                channel=cast("discord.VoiceChannel", self.channel),
                self_deaf=self_deaf,
                self_mute=self_mute,
            )
        except BaseException:  # the gateway refused: nothing connects
            await self._release()
            raise

    @override
    async def on_voice_state_update(self, data: GuildVoiceState, /) -> None:
        """Forward the bot's voice state to the node; without a channel, the bot left.

        lavalink.py sends the channel to the node only with a new voice session, and a move keeps
        the session: its cached session is dropped first, so that the node hears the new channel,
        which DAVE needs.
        """
        channel_id = cast("str | int | None", data["channel_id"])  # None: the bot left
        if channel_id is None:
            if self.confirmed:
                await self._release()
            return
        self.confirmed = True
        player = self.link.client.player_manager.get(self.guild_id)
        if player is not None:
            state = cast("dict[str, str]", player._voice_state)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType]
            if state.get("channelId", str(channel_id)) != str(channel_id):
                state.pop("sessionId", None)
        if (moved := self.client.get_channel(int(channel_id))) is not None:
            self.channel = cast("discord.abc.Connectable", moved)
        await self.link.client.voice_update_handler(
            cast("Any", {"t": "VOICE_STATE_UPDATE", "d": data})
        )

    @override
    async def on_voice_server_update(self, data: VoiceServerUpdate, /) -> None:
        """Forward the voice server to the node."""
        await self.link.client.voice_update_handler(
            cast("Any", {"t": "VOICE_SERVER_UPDATE", "d": data})
        )

    @override
    async def disconnect(self, *, force: bool) -> None:
        """Leave voice and destroy the guild's player, even when the gateway refuses the leave."""
        del force
        guild = cast("discord.VoiceChannel", self.channel).guild
        try:
            await guild.change_voice_state(channel=None)
        finally:
            await self._release()

    async def _release(self) -> None:
        """Forget the connection once: discord.py's record, the plugin's player, the node's.

        The plugin hears of it before the node's answer, during which the bot may connect again.
        """
        if self.released:
            return
        self.released = True
        if self.link.voices.get(self.guild_id) is self:
            del self.link.voices[self.guild_id]
        if self in self.client.voice_clients:  # not after a new gateway session forgot it
            self.cleanup()
        self.link.listener.left(self.guild_id)
        try:
            await self.link.client.player_manager.destroy(self.guild_id)
        except (*UNAVAILABLE, lavalink.RequestError):
            logger.debug("MusicPlayer: the node could not destroy guild %d's player", self.guild_id)


def open_link(user_id: int, node: Node, listener: Listener) -> NodeLink:
    """Create the lavalink.py client for ``node``; call it in the event loop, after READY.

    lavalink.py connects to the node in the background and reconnects with a backoff, except
    after a refused password, which it logs.
    """
    player = type("NodePlayer", (NodePlayer,), {"listener": listener})
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    client: lavalink.Client[NodePlayer] = lavalink.Client(
        user_id, player=player, request_timeout=timeout
    )
    client.add_node(node.host, node.port, node.password, REGION, NAME)
    return NodeLink(client, listener)
