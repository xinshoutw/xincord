"""The Lavalink node through lavalink.py: loads, the guilds' players, events and voice.

lavalink.py 5.11.1 sends the voice state's ``channelId`` that Lavalink 4.2 needs for DAVE.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:84-138
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/util/MusicPlayerUtils.kt:72-82
"""

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .audio import Listener, Loaded, Track
    from .config import Node


class GuildPlayer:
    """One guild's lavalink.py player as the plugin's ``Player``."""

    @property
    def position(self) -> int:
        """The playing song's position, as lavalink.py estimates it."""
        raise NotImplementedError

    async def play(self, track: Track, *, number: int, volume: int) -> None:
        """Play ``track`` from its start, unpaused, at ``volume``; its events carry ``number``."""
        raise NotImplementedError

    async def set_pause(self, paused: bool) -> None:  # noqa: FBT001 - as the Protocol's
        """Pause or resume the song."""
        raise NotImplementedError

    async def set_volume(self, volume: int) -> None:
        """Change the volume."""
        raise NotImplementedError

    async def stop(self) -> None:
        """Stop the song."""
        raise NotImplementedError


class NodeLink:
    """The plugin's lavalink.py client with its one node."""

    @property
    def available(self) -> bool:
        """Whether the node's WebSocket is connected."""
        raise NotImplementedError

    async def load(self, identifier: str) -> Loaded:
        """Load ``identifier`` on the node."""
        raise NotImplementedError

    def voice(self, client: discord.Client, channel: discord.abc.Connectable) -> LavalinkVoice:
        """The voice protocol that ``channel.connect(cls=link.voice)`` connects with."""
        raise NotImplementedError

    async def close(self) -> None:
        """Close the node's connection and the client's session."""
        raise NotImplementedError


class LavalinkVoice(discord.VoiceProtocol):
    """The bot's voice connection in a guild, which the node makes from its voice updates."""

    async def connect(
        self,
        *,
        timeout: float,  # noqa: ASYNC109 - discord.py's signature
        reconnect: bool,
        self_deaf: bool = False,
        self_mute: bool = False,
    ) -> None:
        """Create the guild's player and ask Discord to connect the bot."""
        raise NotImplementedError

    async def on_voice_state_update(self, data: object, /) -> None:
        """Forward the bot's voice state to the node."""
        raise NotImplementedError

    async def on_voice_server_update(self, data: object, /) -> None:
        """Forward the voice server to the node."""
        raise NotImplementedError

    async def disconnect(self, *, force: bool) -> None:
        """Leave voice and destroy the guild's player."""
        raise NotImplementedError


def open_link(user_id: int, node: Node, listener: Listener) -> NodeLink:
    """Create the lavalink.py client for ``node``; call it in the event loop, after READY."""
    raise NotImplementedError
