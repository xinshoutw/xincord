"""v3's eleven guild commands, a base of the cog.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/command/Register.kt:11-154
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:278-731
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/util/MusicPlayerUtils.kt:85-109
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

import discord
from discord import app_commands

from xincord.plugins.redaction import redact

from .audio import LoadKind, NodeUnavailableError
from .display import SEARCH, cut, identifier
from .history import Entry
from .replies import Replies, Screen, guild_of, requester, voice_channel
from .texts import format_traceback

if TYPE_CHECKING:
    from collections import OrderedDict
    from random import Random

    from .audio import Link, Loaded, Track
    from .session import Session

logger = logging.getLogger(__name__)

QUERY_MAX = 500  # v3's setMaxLength(500)
SEARCH_DEADLINE = 2.5  # seconds an autocomplete search may take: Discord waits 3 (v3 waited 10)
SEARCH_MIN = 2  # v3 searched from two characters
CHOICES = 10  # v3's suggestions
CHOICE = 100  # Discord's limit for a suggestion's name and value
SEARCHES = 100  # v3's cache of searches
FOUND = (LoadKind.TRACK, LoadKind.PLAYLIST, LoadKind.SEARCH)  # loads with songs to suggest


class CommandSpec(NamedTuple):
    """One of v3's commands: its ``register.yaml`` key, v3's English description, its handler."""

    key: str
    description: str
    handler: str  # the cog's method


class OptionSpec(NamedTuple):
    """A command's option: its parameter (v3's option name) and v3's English description."""

    parameter: str
    description: str


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
OPTIONS = {
    "play": OptionSpec("query", "Song name, artist, or URL"),
    "skip": OptionSpec("count", "Number of songs to skip (default is 1)"),
    "volume": OptionSpec("level", "Volume level (0-100)"),
}


class Commands(Replies):
    """The commands' handlers, a base of the cog, which sets the attributes."""

    random: Random  # /shuffle's order
    searches: OrderedDict[str, tuple[app_commands.Choice[str], ...]]  # autocomplete's cache
    search_deadline: float

    def command(self, name: str) -> app_commands.Command[Any, ..., None]:
        """Build v3's command ``name``, localized from ``register.yaml``, for every member.

        A guild command without default permissions, as v3's ``DefaultMemberPermissions.ENABLED``;
        the command tree defers it ephemerally, as v3's core did. ``query`` and ``level`` are
        autocompleted.
        """
        lang, spec = self.lang, COMMANDS[name]
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command(name, f"{spec.key}.name"),
            description=lang.command(spec.description, f"{spec.key}.description"),
            callback=getattr(self, spec.handler),
        )
        if (option := OPTIONS.get(name)) is not None:
            prefix = f"{spec.key}.options.{option.parameter}"
            app_commands.rename(
                **{option.parameter: lang.command(option.parameter, f"{prefix}.name")}
            )(command)
            app_commands.describe(
                **{option.parameter: lang.command(option.description, f"{prefix}.description")}
            )(command)
        if name == "play":
            command.autocomplete("query")(self.song_choices)
        elif name == "volume":
            command.autocomplete("level")(self.volume_choices)
        return command

    async def join_voice(self, interaction: discord.Interaction) -> None:
        """``/join``: connect to the member's voice channel, or move there, and delete the reply.

        As v3: a voice channel (no stage); the bot needs Connect, and Move Members for a full
        channel, as JDA checked; no confirmation.
        """
        channel = voice_channel(interaction)
        if channel is None:
            await self.tell(interaction, "join-voice-first")
            return
        if channel.type is not discord.ChannelType.voice:
            await self.tell(interaction, "voice-channel-not-found")
            return
        guild = guild_of(interaction)
        voice = guild.voice_client
        here = voice is not None and getattr(voice.channel, "id", None) == channel.id
        if not here and not _can_join(channel, guild):
            await self.tell(interaction, "cannot-connect")
            return
        try:
            if voice is None:
                await self.connect(channel)
            elif not here:
                await guild.change_voice_state(channel=channel)
        except NodeUnavailableError:
            await self.tell(interaction, "node-unavailable")
            return
        await interaction.delete_original_response()

    async def leave_voice(self, interaction: discord.Interaction) -> None:
        """``/disconnect``: leave voice, which forgets the songs, and delete the reply.

        Any member may, as in v3.
        """
        voice = guild_of(interaction).voice_client
        if voice is None:
            await self.tell(interaction, "not-connected")
            return
        await voice.disconnect(force=True)
        await interaction.delete_original_response()

    async def play_song(
        self,
        interaction: discord.Interaction,
        query: app_commands.Range[str, None, QUERY_MAX],
    ) -> None:
        """``/play``: load the query, add its songs and show the first one's ``play`` panel.

        v3's checks in v3's order; the bot connects to the member's channel when it is in none
        and stays in another one (P4). A search adds its first song, a playlist every song.
        """
        channel = voice_channel(interaction)
        if channel is None:
            await self.tell(interaction, "play-join-voice-first")
            return
        if channel.type is not discord.ChannelType.voice:
            await self.tell(interaction, "voice-channel-not-found")
            return
        guild = guild_of(interaction)
        if guild.voice_client is None:
            if not channel.permissions_for(guild.me).connect:
                await self.tell(interaction, "no-connect-permission")
                return
            if not _can_join(channel, guild):
                await self.tell(interaction, "cannot-connect")
                return
        if not query.strip():
            await self.tell(interaction, "empty-query")
            return
        try:
            if guild.voice_client is None:
                await self.connect(channel)
            loaded = await self.loader().load(identifier(query))
        except NodeUnavailableError:
            await self.tell(interaction, "node-unavailable")
            return
        await self.add(interaction, query, loaded)

    async def add(self, interaction: discord.Interaction, query: str, loaded: Loaded) -> None:
        """Add the loaded songs to the guild's session and show the first one."""
        tracks: tuple[Track, ...]
        match loaded.kind:
            case LoadKind.EMPTY:
                await self.tell(interaction, "no-matches", query=query)
                return
            case LoadKind.ERROR:
                logger.warning("MusicPlayer: the node could not load %r: %s", query, loaded.error)
                await self.tell(interaction, "load-failed", error=loaded.error or "")
                return
            case LoadKind.PLAYLIST:
                tracks = loaded.tracks
            case _:  # a song, or a search's first song
                tracks = loaded.tracks[:1]
        who = requester(interaction.user)
        # v3 refused songs without a title.
        entries = [Entry(track, who) for track in tracks if track.title.strip()]
        if not entries:
            await self.tell(interaction, "empty-playlist")
            return
        session = self.session(guild_of(interaction).id)
        if session.player is None:  # the bot left voice during the load
            await self.tell(interaction, "not-connected")
            return
        added = await session.enqueue(entries)
        if not added.added:
            await self.tell(interaction, "queue-full")
            return
        locale = interaction.locale.value
        content = (
            self.text("queue-truncated", locale, added=added.added, refused=added.refused)
            if added.refused
            else ""
        )
        await self.show(interaction, Screen("play"), session, entry=entries[0], content=content)

    def loader(self) -> Link:
        """The link to the node.

        Raises:
            NodeUnavailableError: No node is connected.
        """
        if self.link is None or not self.link.available:
            raise NodeUnavailableError
        return self.link

    async def connect(self, channel: discord.VoiceChannel) -> None:
        """Connect the bot to ``channel`` through the node, neither deafened nor muted (v3).

        Raises:
            NodeUnavailableError: No node is connected.
        """
        link = self.loader()
        await channel.connect(cls=link.voice, self_deaf=False, self_mute=False)

    def playing(self, interaction: discord.Interaction) -> Session | None:
        """The guild's session when a song plays (or is paused), else None."""
        session = self.sessions.get(guild_of(interaction).id)
        return session if session is not None and session.playing else None

    async def pause_song(self, interaction: discord.Interaction) -> None:
        """``/pause``: pause the song and show the ``pause`` panel; any member, as in v3."""
        if (session := self.playing(interaction)) is None:
            await self.tell(interaction, "nothing-playing")
        elif not await session.pause():
            await self.tell(interaction, "already-paused")
        else:
            await self.show(interaction, Screen("pause"), session)

    async def resume_song(self, interaction: discord.Interaction) -> None:
        """``/resume``: resume the song and show the ``resume`` panel."""
        if (session := self.playing(interaction)) is None:
            await self.tell(interaction, "nothing-playing")
        elif not await session.resume():
            await self.tell(interaction, "already-playing")
        else:
            await self.show(interaction, Screen("resume"), session)

    async def stop_music(self, interaction: discord.Interaction) -> None:
        """``/stop``: forget the songs, unpaused, leave voice (P2) and delete the reply."""
        if (session := self.playing(interaction)) is None:
            await self.tell(interaction, "nothing-playing")
            return
        await session.stop()
        if (voice := guild_of(interaction).voice_client) is not None:
            await voice.disconnect(force=True)
        await interaction.delete_original_response()

    async def skip_songs(
        self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 50] = 1
    ) -> None:
        """``/skip``: skip ``count`` songs and show the ``skip`` panel.

        v3's maximum is the upcoming songs and the playing one: skipping that many ends the list
        (v3 re-showed the last song and never said ``skipped-to-end``).
        """
        if (session := self.playing(interaction)) is None:
            await self.tell(interaction, "nothing-playing")
            return
        most = len(session.history.upcoming) + 1
        if count > most:
            await self.tell(interaction, "skip-too-many", count=most)
        elif (entry := await session.skip_many(count)) is None:
            await self.tell(interaction, "skipped-to-end")
        else:
            await self.show(interaction, Screen("skip"), session, entry=entry)

    async def change_volume(
        self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]
    ) -> None:
        """``/volume``: set the guild's volume and show the ``volume`` panel with both levels.

        The level stays until the plugin unloads, as v3's per-guild player kept it.
        """
        session = self.session(guild_of(interaction).id)
        before = await session.set_volume(level)
        await self.show(interaction, Screen("volume", (before, level)), session)

    async def show_queue(self, interaction: discord.Interaction) -> None:
        """``/queue``: the ``queue`` panel, or ``empty-playlist`` without upcoming songs."""
        session = self.playing(interaction)
        if session is None or not session.history.upcoming:
            await self.tell(interaction, "empty-playlist")
            return
        await self.show(interaction, Screen("queue"), session)

    async def shuffle_queue(self, interaction: discord.Interaction) -> None:
        """``/shuffle``: shuffle the upcoming songs, for a member in voice; no panel, as v3."""
        if voice_channel(interaction) is None:
            await self.tell(interaction, "shuffle-join-voice")
            return
        session = self.sessions.get(guild_of(interaction).id)
        if session is None or not (count := session.shuffle(self.random)):
            await self.tell(interaction, "shuffle-too-few")
            return
        await self.tell(interaction, "shuffled", count=count)

    async def now_playing(self, interaction: discord.Interaction) -> None:
        """``/now-playing``: the ``now-playing`` panel of the song."""
        if (session := self.playing(interaction)) is None:
            await self.tell(interaction, "nothing-playing")
            return
        await self.show(interaction, Screen("now-playing"), session)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """An error in a command: logged with its traceback and answered, as v3's ``Event``.

        A node that stopped answering is no unexpected error: ``node-unavailable``.
        """
        cause = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        if isinstance(cause, NodeUnavailableError):
            await self.tell(interaction, "node-unavailable")
            return
        name = getattr(getattr(error, "command", None), "qualified_name", "?")
        logger.error("MusicPlayer: /%s failed:\n%s", name, redact(format_traceback(cause)))
        await self.report(interaction, "command-error", cause)

    async def song_choices(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """``query``'s suggestions: v3's YouTube search of the input, from two characters.

        Up to ten songs, ``title | author`` within 100 characters and their links as values
        (Discord refuses longer ones), kept for the 100 latest inputs, the oldest out first, as
        v3's cache; a search that takes past Discord's deadline, fails or finds nothing suggests
        nothing and is not kept.
        """
        del interaction
        if len(current) < SEARCH_MIN:
            return []
        if (cached := self.searches.get(current)) is not None:
            return list(cached)
        if self.link is None or not self.link.available:
            return []
        try:
            async with asyncio.timeout(self.search_deadline):
                loaded = await self.link.load(SEARCH + current)
        except TimeoutError, NodeUnavailableError:
            return []
        if loaded.kind not in FOUND:
            return []
        found = tuple(
            app_commands.Choice(
                name=cut(f"{track.title} | {track.author}", CHOICE), value=track.uri
            )
            for track in loaded.tracks
            if track.uri and len(track.uri) <= CHOICE
        )[:CHOICES]
        self.searches[current] = found
        while len(self.searches) > SEARCHES:
            self.searches.popitem(last=False)
        return list(found)

    async def volume_choices(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        """``level``'s suggestion: the guild's volume, as v3's ``current-volume``."""
        del current
        session = self.sessions.get(guild_of(interaction).id)
        volume = self.config.player.default_volume if session is None else session.volume
        name = self.text("current-volume", interaction.locale.value, volume=volume)
        return [app_commands.Choice(name=name, value=volume)]


def _can_join(channel: discord.VoiceChannel, guild: discord.Guild) -> bool:
    """Whether the bot may join ``channel``: Connect, and Move Members when it is full (JDA's)."""
    permissions = channel.permissions_for(guild.me)
    full = 0 < channel.user_limit <= len(channel.voice_states)
    return permissions.connect and (not full or permissions.move_members)
