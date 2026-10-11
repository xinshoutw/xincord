"""``/pause``, ``/resume``, ``/stop``, ``/skip``, ``/volume``, ``/queue``, ``/shuffle`` and
``/now-playing`` with v3's replies.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:473-731
"""

import random
from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import embed_dict
from music_fakes import FakePlayer, song, text
from plugin_fakes import golden
from xincord.plugins.music_player.history import Entry, Requester

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("music_player")
VOICE = 20
ALICE = Requester(1, "Alice", "alice", "https://cdn.example/alice.png")
DELETED: tuple[str, dict[str, object]] = ("delete_original_response", {})


def reply(interaction: FakeInteraction) -> tuple[str, dict[str, Any]]:
    """The last thing the command sent."""
    method, fields = interaction.sent[-1]
    return method, dict(fields)


def told(interaction: FakeInteraction, key: str, **values: object) -> bool:
    """Whether the command's last reply is the en-US text ``key``."""
    return reply(interaction) == ("edit_original_response", {"content": text(key, **values)})


def embeds(interaction: FakeInteraction) -> list[dict[str, Any]]:
    """The embeds of the command's last panel."""
    _, fields = reply(interaction)
    return [embed_dict(embed) for embed in cast("list[Any]", fields["embeds"])]


def seeded(seed: int) -> random.Random:
    """A generator with a repeatable order, which /shuffle takes."""
    return random.Random(seed)  # noqa: S311 - an order, no secret


async def test_pause_and_resume(scene: Scene) -> None:
    """Requirement: Members control playback with v3's replies."""
    player = await scene.playing(1)
    paused, again, resumed, still = (scene.who(None) for _ in range(4))  # no voice check (v3)

    await scene.cog.pause_song(paused.as_interaction())
    await scene.cog.pause_song(again.as_interaction())
    await scene.cog.resume_song(resumed.as_interaction())
    await scene.cog.resume_song(still.as_interaction())

    assert embeds(paused)[0]["color"] == GOLDEN["colors"]["paused"]
    assert told(again, "already-paused")
    assert embeds(resumed)[0]["color"] == GOLDEN["colors"]["playing"]
    assert told(still, "already-playing")
    assert [call for call in player.calls if call[0] == "pause"] == [
        ("pause", True),
        ("pause", False),
    ]


@pytest.mark.parametrize("handler", ["pause_song", "resume_song", "now_playing"])
async def test_nothing_playing(scene: Scene, handler: str) -> None:
    """Requirement: Members control playback with v3's replies."""
    interaction = scene.who(VOICE)

    await getattr(scene.cog, handler)(interaction.as_interaction())

    assert told(interaction, "nothing-playing")


async def test_stop(scene: Scene) -> None:
    """Requirement: Members control playback with v3's replies."""
    player = await scene.playing(1, 2)
    await scene.cog.session(10).pause()
    stop, again = scene.who(None), scene.who(VOICE)

    await scene.cog.stop_music(stop.as_interaction())
    await scene.cog.stop_music(again.as_interaction())

    session = scene.cog.sessions[10]
    assert player.calls[-1] == ("stop", None)
    assert (session.history.entries, session.paused) == ([], False)  # v3 kept the pause (B2)
    assert scene.link.disconnects == [10]  # /stop leaves too (P2)
    assert reply(stop) == DELETED
    assert told(again, "nothing-playing")


async def test_skip(scene: Scene) -> None:
    """Requirement: Members control playback with v3's replies."""
    player = await scene.playing(1, 2, 3, 4)
    too_many, two, to_the_end, nothing = (scene.who(VOICE) for _ in range(4))

    await scene.cog.skip_songs(too_many.as_interaction(), 5)
    await scene.cog.skip_songs(two.as_interaction(), 2)
    await scene.cog.skip_songs(to_the_end.as_interaction(), 2)
    await scene.cog.skip_songs(nothing.as_interaction(), 1)

    assert told(too_many, "skip-too-many", count=4)  # v3's maximum: the upcoming songs and this
    assert embeds(two)[0]["title"] == "Song 3"
    assert told(to_the_end, "skipped-to-end")  # v3 re-showed the last song instead (B17)
    assert told(nothing, "nothing-playing")
    assert player.played()[-1] == ("Song 3", 2, 40)
    assert player.calls[-1] == ("stop", None)


async def test_volume(scene: Scene) -> None:
    """Requirement: Volume, queue, shuffle and now playing keep v3's replies."""
    before, after = scene.who(None), scene.who(None)

    await scene.cog.change_volume(before.as_interaction(), 70)
    player = await scene.playing(1)
    await scene.cog.change_volume(after.as_interaction(), 30)

    assert embeds(before) == [
        {"title": GOLDEN["volume_title"]["en-US"], "color": GOLDEN["colors"]["volume"]}
    ]
    assert player.played() == [("Song 1", 1, 70)]  # songs play at the guild's volume
    assert player.calls[-1] == ("volume", 30)
    assert embeds(after)[0]["title"].endswith(f" 70 {chr(0x279E)} 30")


async def test_queue(scene: Scene) -> None:
    """Requirement: Volume, queue, shuffle and now playing keep v3's replies."""
    await scene.playing(1, 2, 3)
    shown, empty = scene.who(None), scene.who(None)

    await scene.cog.show_queue(shown.as_interaction())
    await scene.cog.session(10).skip_many(2)
    await scene.cog.show_queue(empty.as_interaction())

    track, listing = embeds(shown)
    assert (track["title"], track["color"]) == ("Song 1", GOLDEN["colors"]["queue"])
    assert "footer" not in track  # v3's queue panel has none
    assert listing["fields"][0]["value"].split("\n") == [
        "1. **Song 2** | Band 2 `[03:34]`",
        "2. **Song 3** | Band 3 `[03:34]`",
    ]
    assert told(empty, "empty-playlist")  # v3's reply: a song plays and none waits


async def test_shuffle(scene: Scene) -> None:
    """Requirement: Volume, queue, shuffle and now playing keep v3's replies."""
    scene.cog.random = seeded(5)
    await scene.playing(1, 2)
    outside, one, three = scene.who(None), scene.who(VOICE), scene.who(VOICE)

    await scene.cog.shuffle_queue(outside.as_interaction())
    await scene.cog.shuffle_queue(one.as_interaction())
    await scene.cog.session(10).enqueue([Entry(song(3), ALICE), Entry(song(4), ALICE)])
    await scene.cog.shuffle_queue(three.as_interaction())

    assert told(outside, "shuffle-join-voice")
    assert told(one, "shuffle-too-few")
    assert told(three, "shuffled", count=3)
    expected = ["Song 2", "Song 3", "Song 4"]
    seeded(5).shuffle(expected)
    upcoming = scene.cog.sessions[10].history.upcoming
    assert [entry.track.title for entry in upcoming] == expected


async def test_now_playing(scene: Scene) -> None:
    """Requirement: Volume, queue, shuffle and now playing keep v3's replies."""
    await scene.playing(1, 2)
    shown = scene.who(None)

    await scene.cog.now_playing(shown.as_interaction())

    track = embeds(shown)[0]
    assert (track["title"], track["footer"]["text"]) == ("Song 1", GOLDEN["footer"]["en-US"])


async def test_stop_without_a_voice_connection(scene: Scene) -> None:
    """Requirement: Members control playback with v3's replies."""
    player = FakePlayer()  # a session whose connection Discord dropped as /stop came in
    scene.cog.session(10).attach(player)
    await scene.cog.session(10).enqueue([Entry(song(1), ALICE)])
    stop = scene.who(VOICE)

    await scene.cog.stop_music(stop.as_interaction())

    assert player.calls[-1] == ("stop", None)
    assert scene.link.disconnects == []
    assert reply(stop) == DELETED
