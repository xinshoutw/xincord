"""The voice lifecycle: the idle leave, disconnections, left guilds, READY and the unload.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:19-62
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/GuildMusicManager.kt:59-112
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/util/MusicPlayerUtils.kt:51-65
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import BOT_USER, server_error
from music_fakes import FakeLink
from plugin_fakes import dispatch, until
from xincord.core.bot import Bot
from xincord.plugins.music_player.audio import EndReason
from xincord.plugins.music_player.emojis import FALLBACKS

if TYPE_CHECKING:
    from conftest import Scene
    from plugin_fakes import Ready
    from xincord.plugins.music_player.audio import Listener
    from xincord.plugins.music_player.cog import MusicPlayer
    from xincord.plugins.music_player.config import Node

DELETED: tuple[str, dict[str, object]] = ("delete_original_response", {})
NEVER = """\
lavalink:
  password: "example-password"
player:
  auto_leave_timeout: 0
"""


@dataclass(frozen=True)
class FakeEmoji:
    """An application emoji: its name, and its mention as ``str``."""

    name: str
    id: int

    def __str__(self) -> str:
        """The mention markup."""
        return f"<:{self.name}:{self.id}>"


def fake_link(user_id: int, node: Node, listener: Listener) -> FakeLink:
    """A link to a fake node, as ``open_link`` makes one."""
    del user_id, node, listener
    return FakeLink()


async def started() -> None:
    """Let the tasks that the last change started run up to their first wait."""
    await asyncio.sleep(0)


async def test_idle_timeout(scene: Scene) -> None:
    """Requirement: The bot leaves when idle, disconnected or removed."""
    await scene.playing(1)

    await scene.cog.session(10).ended(1, EndReason.FINISHED)  # the last song ended
    await started()
    assert scene.clock.under_way() == 1
    await scene.clock.advance(600)  # v3's auto_leave_timeout, which v3 never applied (B10)
    await until(lambda: scene.link.disconnects == [10])

    assert scene.clock.waits[-1] == 600.0
    assert scene.cog.sessions[10].player is None


async def test_a_song_starts_before(scene: Scene) -> None:
    """Requirement: The bot leaves when idle, disconnected or removed."""
    await scene.connect()  # idle from the connection, as after /join
    await started()
    assert scene.clock.under_way() == 1

    await scene.playing(1)
    await scene.clock.advance(600)
    await started()

    assert scene.link.disconnects == []
    assert scene.clock.under_way() == 0


@pytest.mark.parametrize("config", [NEVER])
async def test_no_timeout(scene: Scene) -> None:
    """Requirement: The bot leaves when idle, disconnected or removed."""
    await scene.playing(1)

    await scene.cog.session(10).ended(1, EndReason.FINISHED)
    await started()

    assert scene.cog.config.player.auto_leave_timeout == 0
    assert scene.clock.under_way() == 0
    assert scene.cog.sessions[10].player is not None  # still connected
    assert scene.link.disconnects == []
    assert scene.cog.idle == {}


async def test_disconnected_by_someone_else(scene: Scene) -> None:
    """Requirement: The bot leaves when idle, disconnected or removed."""
    await scene.playing(1, 2)
    command = scene.who()
    await scene.cog.now_playing(command.as_interaction())
    assert scene.cog.idle == {}

    scene.guild.voice_client.gone()  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    await until(lambda: DELETED in command.sent)

    session = scene.cog.sessions[10]
    assert (session.player, session.history.entries) == (None, [])
    assert 10 not in scene.link.players
    assert scene.cog.panels.panels == {}


async def test_guild_removed(scene: Scene) -> None:
    """Requirement: The bot leaves when idle, disconnected or removed."""
    await scene.playing(1)
    await scene.cog.session(10).set_volume(70)
    command = scene.who()
    await scene.cog.now_playing(command.as_interaction())

    await dispatch(scene.bot, "guild_remove", scene.guild)
    assert 10 not in scene.cog.sessions  # the volume too
    await until(lambda: DELETED in command.sent)

    assert scene.link.disconnects == [10]
    assert scene.cog.panels.panels == {}


async def test_offline_load(bot: Bot) -> None:
    """Requirement: The node and the emojis load from READY, and unloading leaves voice."""
    cog = cast("MusicPlayer", bot.get_cog("MusicPlayer"))
    opened: list[int] = []

    def open_link(user_id: int, _node: Node, _listener: Listener) -> FakeLink:
        opened.append(user_id)
        return FakeLink()

    cog.open_link = cast("Any", open_link)
    starting = cog.starting

    await bot.remove_cog("MusicPlayer")

    assert starting is not None
    assert starting.cancelled()  # it waited for a READY that never came
    assert opened == []


async def test_emojis(
    bot: Bot, ready: Ready, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The node and the emojis load from READY, and unloading leaves voice."""
    cog = cast("MusicPlayer", bot.get_cog("MusicPlayer"))
    link = FakeLink()
    opened: list[tuple[int, Node, Listener]] = []

    def open_link(user_id: int, node: Node, listener: Listener) -> FakeLink:
        opened.append((user_id, node, listener))
        return link

    async def emojis(_bot: Bot) -> list[FakeEmoji]:
        return [
            FakeEmoji("music_player__media_play", 1395593807352954961),
            FakeEmoji("music_player__line_white_start", 1395593807352954962),
            FakeEmoji("unrelated", 1395593807352954963),
        ]

    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))
    monkeypatch.setattr(Bot, "fetch_application_emojis", emojis)
    cog.open_link = cast("Any", open_link)
    assert cog.starting is not None

    with caplog.at_level(logging.WARNING):
        ready.set()
        await cog.starting

    assert opened == [(BOT_USER.id, cog.config.lavalink, cog)]
    assert cog.link is link
    assert cog.emojis["media_play"] == "<:music_player__media_play:1395593807352954961>"
    assert cog.emojis["progress_white_start"] == (
        "<:music_player__line_white_start:1395593807352954962>"
    )
    assert cog.emojis["media_pause"] == FALLBACKS["media_pause"]
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "music_player__media_pause" in warnings[0].getMessage()
    assert "music_player__media_play," not in warnings[0].getMessage()


async def test_emojis_unreadable(
    bot: Bot, ready: Ready, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The node and the emojis load from READY, and unloading leaves voice."""
    cog = cast("MusicPlayer", bot.get_cog("MusicPlayer"))

    async def emojis(_bot: Bot) -> list[FakeEmoji]:
        raise server_error()

    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))
    monkeypatch.setattr(Bot, "fetch_application_emojis", emojis)
    cog.open_link = cast("Any", fake_link)
    assert cog.starting is not None

    with caplog.at_level(logging.WARNING):
        ready.set()
        await cog.starting

    assert dict(cog.emojis) == FALLBACKS
    assert "emojis" in caplog.text


async def test_unload(scene: Scene) -> None:
    """Requirement: The node and the emojis load from READY, and unloading leaves voice."""
    await scene.playing(1)
    command = scene.who()
    cog = scene.cog
    await cog.now_playing(command.as_interaction())

    await scene.bot.remove_cog("MusicPlayer")

    assert scene.link.disconnects == [10]  # v3 left its players running (B23)
    assert DELETED in command.sent
    assert scene.link.closed is True
    assert cog.panels.panels == {}


async def test_all_the_emojis(bot: Bot, ready: Ready, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: The node and the emojis load from READY, and unloading leaves voice."""
    cog = cast("MusicPlayer", bot.get_cog("MusicPlayer"))
    names = cog.config.emojis.model_dump()

    async def emojis(_bot: Bot) -> list[FakeEmoji]:
        return [FakeEmoji(name, 1395593807352954900 + n) for n, name in enumerate(names.values())]

    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))
    monkeypatch.setattr(Bot, "fetch_application_emojis", emojis)
    cog.open_link = cast("Any", fake_link)
    assert cog.starting is not None

    ready.set()
    await cog.starting

    assert all(mention.startswith("<:music_player__") for mention in cog.emojis.values())


async def test_guild_removed_without_voice(scene: Scene) -> None:
    """Requirement: The bot leaves when idle, disconnected or removed."""
    await scene.cog.session(10).set_volume(70)  # a volume panel, without voice
    command = scene.who()
    await scene.cog.change_volume(command.as_interaction(), 60)

    await dispatch(scene.bot, "guild_remove", scene.guild)

    assert 10 not in scene.cog.sessions
    assert DELETED in command.sent
    assert scene.link.disconnects == []
