"""``/play``: the member's checks, the node's load, and the ``play`` panel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:365-471
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/GuildMusicManager.kt:127-164
"""

import asyncio
from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import embed_dict
from music_fakes import song, text
from plugin_fakes import until
from xincord.plugins.music_player.audio import LoadKind

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

VOICE, STAGE, LOCKED, FULL, OTHER = 20, 21, 22, 23, 24
PLAYLIST = "https://www.youtube.com/playlist?list=mix"


def panel(interaction: FakeInteraction) -> dict[str, Any]:
    """The last edit of the response: content, embeds and view."""
    method, fields = interaction.sent[-1]
    assert method == "edit_original_response"
    return dict(fields)


def title(fields: dict[str, Any]) -> str:
    """The title of a panel's first embed: the song's."""
    embeds = cast("list[Any]", fields["embeds"])
    return str(embed_dict(embeds[0])["title"])


async def test_play_a_search(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer("ytsearch:never gonna", LoadKind.SEARCH, song(1), song(2))
    interaction = scene.who(VOICE)

    await scene.cog.play_song(interaction.as_interaction(), "never gonna")

    assert scene.link.loads == ["ytsearch:never gonna"]
    assert scene.link.connects == [(10, VOICE)]
    assert scene.player().played() == [("Song 1", 1, 40)]  # a search's first song only
    fields = panel(interaction)
    assert fields["content"] == ""
    assert title(fields) == "Song 1"
    embed = embed_dict(cast("list[Any]", fields["embeds"])[0])
    assert embed["footer"]["text"] == "Requested by alice"
    assert embed["color"] == 0x68C06E  # playing


async def test_play_a_playlist(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer("ytsearch:first", LoadKind.SEARCH, song(1))
    scene.answer(PLAYLIST, LoadKind.PLAYLIST, song(2), song(3), song(4))
    await scene.cog.play_song(scene.who(VOICE).as_interaction(), "first")
    interaction = scene.who(VOICE)

    await scene.cog.play_song(interaction.as_interaction(), PLAYLIST)

    session = scene.cog.sessions[10]
    assert [entry.track.title for entry in session.history.upcoming] == [
        "Song 2",
        "Song 3",
        "Song 4",
    ]
    assert scene.player().played() == [("Song 1", 1, 40)]  # it waits after the playing one
    assert title(panel(interaction)) == "Song 2"  # v3 showed the playlist's first song


async def test_another_channel(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer("https://youtu.be/x", LoadKind.TRACK, song(1))
    await scene.connect(OTHER)
    interaction = scene.who(VOICE)

    await scene.cog.play_song(interaction.as_interaction(), "https://youtu.be/x")

    assert scene.link.connects == [(10, OTHER)]  # the bot stays where it is (P4)
    assert scene.guild.voice_moves == []
    assert scene.player().played() == [("Song 1", 1, 40)]


@pytest.mark.parametrize(
    ("channel", "query", "key", "values"),
    [
        pytest.param(None, "never gonna", "play-join-voice-first", {}, id="outside voice"),
        pytest.param(STAGE, "never gonna", "voice-channel-not-found", {}, id="stage"),
        pytest.param(LOCKED, "never gonna", "no-connect-permission", {}, id="no Connect"),
        pytest.param(FULL, "never gonna", "cannot-connect", {}, id="full channel"),
        pytest.param(VOICE, "   ", "empty-query", {}, id="blank query"),
        pytest.param(VOICE, "nothing", "no-matches", {"query": "nothing"}, id="no match"),
        pytest.param(
            VOICE, "broken", "load-failed", {"error": "This video is unavailable"}, id="error"
        ),
        pytest.param(VOICE, PLAYLIST, "empty-playlist", {}, id="empty playlist"),
    ],
)
async def test_refusals(
    scene: Scene, channel: int | None, query: str, key: str, values: dict[str, str]
) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer("ytsearch:never gonna", LoadKind.SEARCH, song(1))
    scene.answer("ytsearch:broken", LoadKind.ERROR, error="This video is unavailable")
    scene.answer(PLAYLIST, LoadKind.PLAYLIST)
    interaction = scene.who(channel)

    await scene.cog.play_song(interaction.as_interaction(), query)

    assert interaction.sent == [("edit_original_response", {"content": text(key, **values)})]
    assert scene.link.players.get(10) is None or scene.player().played() == []


async def test_no_node(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.link.available = False
    interaction = scene.who(VOICE)

    await scene.cog.play_song(interaction.as_interaction(), "never gonna")

    assert interaction.sent == [("edit_original_response", {"content": text("node-unavailable")})]
    assert scene.link.connects == []


async def test_full_history(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer(PLAYLIST, LoadKind.PLAYLIST, *(song(number) for number in range(241)))
    scene.answer("ytsearch:more", LoadKind.SEARCH, song(999))
    truncated = scene.who(VOICE)

    await scene.cog.play_song(truncated.as_interaction(), PLAYLIST)

    assert panel(truncated)["content"] == text("queue-truncated", added=240, refused=1)
    assert title(panel(truncated)) == "Song 0"
    full = scene.who(VOICE)

    await scene.cog.play_song(full.as_interaction(), "more")

    assert full.sent[-1] == ("edit_original_response", {"content": text("queue-full")})


async def test_the_bot_left_during_the_load(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer("ytsearch:never gonna", LoadKind.SEARCH, song(1))
    await scene.connect()
    scene.link.gate = asyncio.Event()  # the load waits
    interaction = scene.who(VOICE)
    playing = asyncio.create_task(scene.cog.play_song(interaction.as_interaction(), "never gonna"))
    await until(lambda: scene.link.loads == ["ytsearch:never gonna"])

    await scene.cog.leave_voice(scene.who().as_interaction())  # someone sent the bot away
    scene.link.gate.set()
    await playing

    assert interaction.sent == [("edit_original_response", {"content": text("not-connected")})]
    assert scene.cog.sessions[10].history.entries == []
    assert scene.cog.panels.panels == {}


@pytest.mark.xfail(strict=True, reason="Play queues songs and starts them")
async def test_the_bot_left_while_the_songs_waited(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer("ytsearch:never gonna", LoadKind.SEARCH, song(1))
    await scene.connect()
    session = scene.cog.sessions[10]
    interaction = scene.who(VOICE)
    async with session.lock:  # the player is busy, as with another member's /skip
        playing = asyncio.create_task(
            scene.cog.play_song(interaction.as_interaction(), "never gonna")
        )
        await until(lambda: scene.link.loads == ["ytsearch:never gonna"])
        session.detach()  # the bot left voice while the songs waited for the player
    await playing

    assert interaction.sent == [("edit_original_response", {"content": text("not-connected")})]
    assert session.history.entries == []
