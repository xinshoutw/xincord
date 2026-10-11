"""v3's eleven guild commands, a base of the cog.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/command/Register.kt:11-154
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:278-731
"""

from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    import discord
    from discord import app_commands


class CommandSpec(NamedTuple):
    """One of v3's commands: its ``register.yaml`` key, v3's English description, its handler."""

    key: str
    description: str
    handler: str  # the cog's method


# v3's commands in v3's order (Register.kt:78-155), with the descriptions of its code.
COMMANDS = {
    "join": CommandSpec("join", "Make the bot join your voice channel", "join_voice"),
    "disconnect": CommandSpec("disconnect", "Make the bot leave the voice channel", "leave_voice"),
    "play": CommandSpec("play", "Play music", "play_song"),
    "pause": CommandSpec("pause", "Pause the currently playing music", "pause_song"),
    "resume": CommandSpec("resume", "Resume the paused music", "resume_song"),
    "stop": CommandSpec("stop", "Stop playing and clear the playlist", "stop_music"),
    "skip": CommandSpec("skip", "Skip the currently playing song", "skip_songs"),
    "volume": CommandSpec("volume", "Set the player volume", "change_volume"),
    "queue": CommandSpec("queue", "View the current playlist", "show_queue"),
    "shuffle": CommandSpec("shuffle", "Shuffle the current playlist once", "shuffle_queue"),
    "now-playing": CommandSpec(
        "now_playing", "View detailed information of the currently playing song", "now_playing"
    ),
}


class Commands:
    """The commands' handlers, a base of the cog, which sets the attributes."""

    def command(self, name: str) -> app_commands.Command[Any, ..., None]:
        """Build v3's command ``name``, localized from ``register.yaml``, for every member."""
        raise NotImplementedError

    async def join_voice(self, interaction: discord.Interaction) -> None:
        """``/join``: connect to the member's voice channel, or move there."""
        raise NotImplementedError

    async def leave_voice(self, interaction: discord.Interaction) -> None:
        """``/disconnect``: stop the player and leave."""
        raise NotImplementedError

    async def play_song(self, interaction: discord.Interaction, query: str) -> None:
        """``/play``: load the query, add its songs and show the first one."""
        raise NotImplementedError
