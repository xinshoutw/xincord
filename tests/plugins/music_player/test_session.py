"""One guild's history on its player: the songs started, the node's events, the controls.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/GuildMusicManager.kt:127-237
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/TrackSchedulerCompat.kt:32-62
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/HistoryIndexManager.kt:41-157
"""

import logging
import random
from typing import TYPE_CHECKING, cast

import pytest

from music_fakes import FakePlayer
from xincord.plugins.music_player.audio import EndReason, Track
from xincord.plugins.music_player.history import Entry, LoopMode, Requester
from xincord.plugins.music_player.session import Session

if TYPE_CHECKING:
    from conftest import Scene

ALICE = Requester(7, "Alice", "alice", "https://cdn.example/alice.png")
VOLUME = 40


def song(number: int) -> Entry:
    """A song added by Alice."""
    return Entry(Track(f"QA{number}", f"Song {number}", "Band", None, str(number), 1000), ALICE)


def session_with(player: FakePlayer, changes: list[bool] | None = None) -> Session:
    """A connected session at the default volume that records when it starts or stops playing."""
    seen = changes if changes is not None else []

    def changed(session: Session) -> None:
        seen.append(session.playing)

    session = Session(10, VOLUME, changed)
    session.attach(player)
    return session


async def test_sequential_and_loop() -> None:
    """Requirement: Playback follows the node's events."""
    player = FakePlayer()
    session = session_with(player)
    await session.enqueue([song(1), song(2)])

    await session.ended(1, EndReason.FINISHED)
    assert session.toggle_loop() is LoopMode.SINGLE
    await session.ended(2, EndReason.FINISHED)

    assert player.played() == [("Song 1", 1, VOLUME), ("Song 2", 2, VOLUME), ("Song 2", 3, VOLUME)]


async def test_end_of_the_list() -> None:
    """Requirement: Playback follows the node's events."""
    player = FakePlayer()
    changes: list[bool] = []
    session = session_with(player, changes)
    await session.enqueue([song(1)])

    await session.ended(1, EndReason.FINISHED)

    assert player.played() == [("Song 1", 1, VOLUME)]
    assert session.playing is False
    assert changes[-2:] == [True, False]  # it started, then went idle


@pytest.mark.parametrize("loop", [LoopMode.SEQUENTIAL, LoopMode.SINGLE])
async def test_failed_and_stuck_songs(loop: LoopMode, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Playback follows the node's events."""
    player = FakePlayer()
    session = session_with(player)
    if session.loop is not loop:
        session.toggle_loop()
    await session.enqueue([song(1), song(2), song(3)])

    with caplog.at_level(logging.WARNING):
        await session.ended(1, EndReason.LOAD_FAILED)
        await session.stuck(2)
        await session.stuck(3)

    assert player.played() == [("Song 1", 1, VOLUME), ("Song 2", 2, VOLUME), ("Song 3", 3, VOLUME)]
    assert player.calls[-1] == ("stop", None)  # the stuck last song stops
    assert session.playing is False
    for title in ("Song 1", "Song 2", "Song 3"):
        assert title in caplog.text


async def test_stale_events() -> None:
    """Requirement: Playback follows the node's events."""
    player = FakePlayer()
    session = session_with(player)
    await session.enqueue([song(1), song(2), song(3)])
    await session.skip()  # Song 2 replaces Song 1 as number 2

    await session.ended(1, EndReason.FINISHED)  # Song 1's natural end crossed the skip
    await session.ended(2, EndReason.STOPPED)
    await session.ended(2, EndReason.REPLACED)
    await session.stuck(1)

    assert player.played() == [("Song 1", 1, VOLUME), ("Song 2", 2, VOLUME)]
    assert session.history.current == song(2)


async def test_cleanup() -> None:
    """Requirement: Playback follows the node's events."""
    player = FakePlayer()
    session = session_with(player)
    await session.enqueue([song(1), song(2)])

    await session.ended(1, EndReason.CLEANUP)  # the node dropped the song
    added = await session.enqueue([song(3)])

    assert added is not None
    assert added.start == song(3)
    assert player.played()[-1] == ("Song 3", 2, VOLUME)


async def test_pause_resume_and_stop() -> None:
    """Requirement: Members control playback with v3's replies."""
    player = FakePlayer()
    session = session_with(player)
    assert await session.pause() is False  # nothing plays
    await session.enqueue([song(1), song(2)])

    assert (await session.pause(), await session.pause()) == (True, False)
    assert (await session.resume(), await session.resume()) == (True, False)
    await session.pause()
    await session.stop()

    assert player.calls[1:] == [
        ("pause", True),
        ("pause", False),
        ("pause", True),
        ("stop", None),
    ]
    assert (session.playing, session.paused, session.history.entries) == (False, False, [])


async def test_skip_unpauses() -> None:
    """Requirement: Members control playback with v3's replies."""
    player = FakePlayer()
    session = session_with(player)
    await session.enqueue([song(1), song(2), song(3), song(4)])
    await session.pause()

    assert await session.skip_many(2) == song(3)
    assert session.paused is False  # every song starts unpaused
    assert await session.skip() == song(4)
    assert await session.skip() is None  # the last song: nothing changes
    assert await session.skip_many(1) is None  # past it: the list ends

    assert player.played()[-2:] == [("Song 3", 2, VOLUME), ("Song 4", 3, VOLUME)]
    assert player.calls[-1] == ("stop", None)
    assert session.playing is False


async def test_previous_and_loop() -> None:
    """Requirement: Panel buttons control the guild's player."""
    player = FakePlayer()
    session = session_with(player)
    await session.enqueue([song(1), song(2)])
    await session.skip()
    await session.pause()

    player.position = 7000
    restarted = await session.previous()
    player.position = 1000
    went_back = await session.previous()

    assert (restarted, went_back) == (song(2), song(1))
    assert session.paused is False  # v3's previous kept the pause (B22)
    assert player.played()[-2:] == [("Song 2", 3, VOLUME), ("Song 1", 4, VOLUME)]
    assert session.position() == 1000
    assert [session.toggle_loop(), session.toggle_loop()] == [LoopMode.SINGLE, LoopMode.SEQUENTIAL]


async def test_volume_and_shuffle() -> None:
    """Requirement: Volume, queue, shuffle and now playing keep v3's replies."""
    player = FakePlayer()
    session = session_with(player)
    await session.enqueue([song(1), song(2), song(3)])

    before = await session.set_volume(70)
    await session.skip()

    assert before == VOLUME
    assert player.calls[1] == ("volume", 70)
    assert player.played()[-1] == ("Song 2", 2, 70)  # the next song plays at the new volume
    assert session.shuffle(random.Random(3)) == 0  # noqa: S311 - an order, no secret


async def test_detach() -> None:
    """Requirement: The bot leaves when idle, disconnected or removed."""
    player = FakePlayer()
    changes: list[bool] = []
    session = session_with(player, changes)
    await session.enqueue([song(1)])
    await session.set_volume(70)
    session.toggle_loop()

    session.detach()
    await session.ended(1, EndReason.FINISHED)  # an event after the disconnection

    assert (session.player, session.playing, session.history.entries) == (None, False, [])
    assert (session.volume, session.loop) == (70, LoopMode.SINGLE)  # v3 kept both per guild
    assert session.position() == 0
    assert changes[-1] is False
    assert player.played() == [("Song 1", 1, VOLUME)]


async def test_songs_wait_while_one_plays() -> None:
    """Requirement: Playback follows the node's events."""
    player = FakePlayer()
    session = session_with(player)
    await session.enqueue([song(1)])

    added = await session.enqueue([song(2)])
    await session.ended(1, EndReason.FINISHED)

    assert added is not None
    assert added.start is None
    assert player.played() == [("Song 1", 1, VOLUME), ("Song 2", 2, VOLUME)]


async def test_controls_while_nothing_plays() -> None:
    """Requirement: Members control playback with v3's replies."""
    session = Session(10, VOLUME, lambda _session: None)

    assert await session.skip() is None
    assert await session.skip_many(1) is None
    await session.stop()  # no player: nothing to stop
    assert session.playing is False


async def test_volume_without_a_player() -> None:
    """Requirement: Volume, queue, shuffle and now playing keep v3's replies."""
    session = Session(10, VOLUME, lambda _session: None)

    assert await session.set_volume(70) == VOLUME
    player = FakePlayer()
    session.attach(player)
    await session.enqueue([song(1)])

    assert player.calls == [("play", ("Song 1", 1, 70))]


async def test_songs_added_while_disconnected() -> None:
    """Requirement: Play queues songs and starts them."""
    session = Session(10, VOLUME, lambda _session: None)

    added = await session.enqueue([song(1)])

    assert added is None  # the bot is not in voice: nothing is added
    assert session.playing is False
    assert session.history.entries == []


async def test_a_refused_start() -> None:
    """Requirement: Errors are reported as v3 did."""
    player = FakePlayer(error=RuntimeError("the node refused"))
    session = session_with(player)

    with pytest.raises(RuntimeError, match="the node refused"):
        await session.enqueue([song(1)])

    assert session.playing is False  # nothing plays, and the song stays for a later start
    assert session.history.entries == [song(1)]


def test_no_current_song() -> None:
    """Requirement: Panels show v3's track layout."""
    session = Session(10, VOLUME, lambda _session: None)

    with pytest.raises(LookupError, match="guild 10 has no song"):
        session.current()


async def test_the_node_reaches_the_session(scene: Scene) -> None:
    """Requirement: Playback follows the node's events."""
    player = await scene.playing(1, 2, 3)

    await scene.cog.ended(10, 1, EndReason.FINISHED)
    await scene.cog.stuck(10, 2)
    await scene.cog.ended(11, 1, EndReason.FINISHED)  # a guild without music
    await scene.cog.stuck(11, 1)

    assert [title for title, _, _ in cast("list[tuple[str, int, int]]", player.played())] == [
        "Song 1",
        "Song 2",
        "Song 3",
    ]
