"""Fixtures for the MusicPlayer tests: the plugin loads through its real entry point, offline.

READY never comes unless a test sets it, so the plugin's startup task waits for it; the tasks left
running are cancelled when the test ends. No test reaches the network: aiohttp refuses every host
but this machine's, where the fake Lavalink node listens.
"""

import errno
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import discord
import pytest

from discord_fakes import (
    BOT_USER,
    FakeAsset,
    FakeGuild,
    FakeInteraction,
    FakeMember,
    FakeVoiceChannel,
    Sent,
    voice_state,
)
from music_fakes import FakeLink, FakePlayer, loaded, song
from plugin_fakes import Ready, load_plugin
from xincord.plugins.music_player.history import Entry, Requester

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.music_player.audio import LoadKind, Track
    from xincord.plugins.music_player.cog import MusicPlayer

PACKAGE = "xincord.plugins.music_player"
LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
# The bundled config with an example password, which the bundled file leaves to the operator.
CONFIG = """\
lavalink:
  host: "lavalink"
  port: 2333
  password: "example-password"
"""


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py drops a plugin's modules when its setup fails (an invalid config), and the next load
    imports new ones, whose classes differ from those that the test modules imported.
    """
    kept = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(f"{PACKAGE}.")
    }
    yield
    sys.modules.update(kept)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reaches the network: aiohttp refuses every host but this machine's.

    The fake Lavalink node listens on 127.0.0.1; a plugin that a test failed to give its fake link
    would otherwise look for the compose host `lavalink`.
    """
    resolve = aiohttp.TCPConnector._resolve_host  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    async def local_only(
        connector: aiohttp.TCPConnector, host: str, port: int, traces: object = None
    ) -> object:
        if host not in LOCAL_HOSTS:
            msg = f"the tests do not reach the network: {host}"
            raise OSError(errno.EHOSTUNREACH, msg)  # aiohttp's error shows its strerror
        return await resolve(connector, host, port, cast("Any", traces))

    monkeypatch.setattr(aiohttp.TCPConnector, "_resolve_host", local_only)


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the startup task waits for it, and is stopped at the end."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@pytest.fixture
def config() -> str | None:
    """The plugin's config.yaml: the bundled one with an example password, unless parametrized."""
    return CONFIG


@pytest.fixture
async def bot(store: Store, tmp_path: Path, config: str | None) -> Bot:
    """A bot that loaded the plugin with ``config``, offline; its startup waits for READY."""
    return await load_plugin("MusicPlayer", tmp_path / "plugins", store, config=config)


# The guild's voice channels: one the bot joins, a stage, one without Connect, and a full one.
VOICE, STAGE, LOCKED, FULL, OTHER = 20, 21, 22, 23, 24
NO_CONNECT = discord.Permissions(view_channel=True, speak=True)
CAN_CONNECT = discord.Permissions(view_channel=True, connect=True, speak=True)


@dataclass
class Scene:
    """The plugin loaded offline with a fake link, a guild with voice channels, and members."""

    bot: Bot
    link: FakeLink
    guild: FakeGuild
    sent: list[Sent] = field(default_factory=list[Sent])

    @property
    def cog(self) -> MusicPlayer:
        """The loaded plugin's cog."""
        return cast("MusicPlayer", self.bot.get_cog("MusicPlayer"))

    def channel(self, channel_id: int) -> FakeVoiceChannel:
        """The guild's voice channel ``channel_id``."""
        found = self.guild.get_channel(channel_id)
        assert isinstance(found, FakeVoiceChannel)
        return found

    def member(self, channel: int | None = VOICE, *, user_id: int = 1) -> FakeMember:
        """A member of the guild, in voice channel ``channel`` (None: outside voice)."""
        return FakeMember(
            guild=self.guild,
            id=user_id,
            name="alice",
            global_name="Alice",
            avatar=FakeAsset("https://cdn.example/alice.png"),
            voice=voice_state(None if channel is None else self.channel(channel)),
        )

    def who(
        self,
        channel: int | None = VOICE,
        *,
        locale: discord.Locale = discord.Locale.american_english,
        user_id: int = 1,
    ) -> FakeInteraction:
        """A command of a member in voice channel ``channel``, in ``locale``; its ``sent`` holds
        its own responses only."""
        return FakeInteraction(
            data={},
            user=self.member(channel, user_id=user_id),
            guild=self.guild,
            locale=locale,
            client=SimpleNamespace(user=BOT_USER),
        )

    def answer(self, identifier: str, kind: LoadKind, *tracks: Track, error: str = "") -> None:
        """Let the node answer a load of ``identifier``."""
        self.link.answers[identifier] = loaded(kind, *tracks, error=error or None)

    async def connect(self, channel: int = VOICE) -> FakePlayer:
        """Connect the bot to ``channel`` as the plugin does, and return the guild's player."""
        await self.channel(channel).connect(cls=self.link.voice)
        return self.link.players[self.guild.id]

    def player(self) -> FakePlayer:
        """The guild's player on the node."""
        return self.link.players[self.guild.id]

    async def playing(self, *numbers: int) -> FakePlayer:
        """Connect the bot and add songs ``numbers`` as Alice; the first plays."""
        player = await self.connect()
        alice = Requester(1, "Alice", "alice", "https://cdn.example/alice.png")
        await self.cog.session(self.guild.id).enqueue([Entry(song(n), alice) for n in numbers])
        return player


@pytest.fixture
async def scene(store: Store, tmp_path: Path, config: str | None) -> Scene:
    """The plugin loaded with ``config``; its link is a fake node's, as after READY."""
    bot = await load_plugin("MusicPlayer", tmp_path / "plugins", store, config=config)
    sent: list[Sent] = []
    guild = FakeGuild(id=10, name="guild")
    full = FakeVoiceChannel(sent=sent, id=FULL, name="full", guild=guild, user_limit=1)
    full.voice_states = {7: object()}
    guild.channels = [
        FakeVoiceChannel(
            sent=sent, id=VOICE, name="music", guild=guild, bot_permissions=CAN_CONNECT
        ),
        FakeVoiceChannel(
            sent=sent,
            id=STAGE,
            name="stage",
            guild=guild,
            type=discord.ChannelType.stage_voice,
            bot_permissions=CAN_CONNECT,
        ),
        FakeVoiceChannel(
            sent=sent, id=LOCKED, name="locked", guild=guild, bot_permissions=NO_CONNECT
        ),
        full,
        FakeVoiceChannel(
            sent=sent, id=OTHER, name="other", guild=guild, bot_permissions=CAN_CONNECT
        ),
    ]
    full.bot_permissions = CAN_CONNECT
    link = FakeLink()
    scene = Scene(bot, link, guild, sent)
    link.listener = cast("Any", scene.cog)
    scene.cog.link = cast("Any", link)
    return scene
