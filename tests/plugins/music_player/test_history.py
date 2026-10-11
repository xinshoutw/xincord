"""One guild's history: v3's order of play, without its defects."""

import random

from xincord.plugins.music_player.audio import Track
from xincord.plugins.music_player.history import Added, Entry, History, LoopMode, Requester

ALICE = Requester(7, "Alice", "alice", "https://cdn.example/alice.png")


def song(number: int) -> Entry:
    """A song of the history, added by Alice."""
    return Entry(Track(f"QA{number}", f"Song {number}", "Band", None, str(number), 1000), ALICE)


def seeded(seed: int) -> random.Random:
    """A generator with a repeatable order, which the plugin's shuffle takes."""
    return random.Random(seed)  # noqa: S311 - an order, no secret


def titles(entries: list[Entry]) -> list[str]:
    """The songs' titles, in order."""
    return [entry.track.title for entry in entries]


def test_first_and_later_songs() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History()

    first = history.add([song(1)])
    second = history.add([song(2)])

    assert first == Added(1, 0, song(1))
    assert second == Added(1, 0, None)  # it waits after the playing one
    assert (history.index, history.active) == (0, True)
    assert titles(history.upcoming) == ["Song 2"]


def test_a_song_added_after_the_end() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History()
    history.add([song(1), song(2)])
    history.ended(LoopMode.SEQUENTIAL, failed=False)
    history.ended(LoopMode.SEQUENTIAL, failed=False)  # the last song ended: idle

    added = history.add([song(3)])

    # v3 started only a first song: this one was queued and never played (bug B1).
    assert added == Added(1, 0, song(3))
    assert (history.index, history.active) == (2, True)
    assert titles(history.entries) == ["Song 1", "Song 2", "Song 3"]
    assert history.previous(0) == song(2)  # the ended songs stay behind it


def test_skip() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History()
    history.add([song(1), song(2)])

    assert history.skip() == song(2)
    assert history.skip() is None  # at the last song, the index stays
    assert (history.index, history.active) == (1, True)


def test_skip_many() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History()
    history.add([song(1), song(2), song(3), song(4)])

    assert history.skip_many(2) == song(3)  # the inventory's vector: [A,B,C,D] at A, 2 -> C
    assert history.skip_many(1) == song(4)
    assert history.skip_many(1) is None  # past the last song: the list ends
    assert (history.index, history.active) == (3, False)
    assert history.upcoming == []


def test_previous() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History()
    history.add([song(1), song(2), song(3)])

    assert history.previous(0) == song(1)  # no previous song: restart
    history.skip()
    assert history.previous(5000) == song(2)  # v3's threshold: restart from 5000 ms
    assert history.index == 1
    assert history.previous(4999) == song(1)  # before it: back one
    assert history.index == 0


def test_shuffle() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History()
    history.add([song(1), song(2), song(3)])
    history.skip()

    assert history.shuffle(seeded(1)) == 0  # one upcoming song: nothing to shuffle

    history.add([song(n) for n in range(4, 9)])
    expected = [song(n) for n in range(3, 9)]
    seeded(7).shuffle(expected)

    assert history.shuffle(seeded(7)) == 6
    assert history.entries[:2] == [song(1), song(2)]  # the played and the current songs stay
    assert history.upcoming == expected
    assert history.index == 1


def test_full_history() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History(limit=5)
    history.add([song(1), song(2), song(3)])
    history.skip()
    history.skip()  # Song 3 plays; Song 1 and 2 were played

    made_room = history.add([song(n) for n in range(4, 8)])
    full = history.add([song(8), song(9)])

    # Played songs leave first and the index follows; v3 then dropped new songs silently (B8).
    assert made_room == Added(4, 0, None)
    assert titles(history.entries) == ["Song 3", "Song 4", "Song 5", "Song 6", "Song 7"]
    assert history.index == 0
    assert full == Added(0, 2, None)


def test_full_history_after_the_end() -> None:
    """Requirement: The history keeps v3's order of play."""
    history = History(limit=3)
    history.add([song(1), song(2), song(3)])
    history.skip_many(3)  # the list ended: all three were played

    added = history.add([song(4), song(5), song(6), song(7)])

    assert added == Added(3, 1, song(4))
    assert titles(history.entries) == ["Song 4", "Song 5", "Song 6"]
    assert (history.index, history.active) == (0, True)


def test_ends() -> None:
    """Requirement: Playback follows the node's events."""
    history = History()
    history.add([song(1), song(2)])

    assert history.ended(LoopMode.SINGLE, failed=False) == song(1)  # single-song loop: again
    assert history.ended(LoopMode.SINGLE, failed=True) == song(2)  # never a failed song (B9)
    assert history.ended(LoopMode.SEQUENTIAL, failed=False) is None  # the end of the list
    assert (history.index, history.active) == (1, False)


def test_idle() -> None:
    """Requirement: Playback follows the node's events."""
    history = History()
    history.add([song(1), song(2)])

    history.idle()  # the node dropped the song

    assert history.active is False
    assert titles(history.entries) == ["Song 1", "Song 2"]
    assert history.add([song(3)]).start == song(3)


def test_stop() -> None:
    """Requirement: Members control playback with v3's replies."""
    history = History()
    history.add([song(1), song(2)])

    history.stop()

    assert (history.entries, history.index, history.active) == ([], 0, False)
    assert history.current is None
