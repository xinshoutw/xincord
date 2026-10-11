"""``/play``: the member's checks, the node's load, and the ``play`` panel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:365-471
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/music/GuildMusicManager.kt:127-164
"""

from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import embed_dict
from music_fakes import song, text
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


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Play queues songs and starts them"
)
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


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Play queues songs and starts them"
)
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


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Play queues songs and starts them"
)
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
@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Play queues songs and starts them"
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


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Play queues songs and starts them"
)
async def test_no_node(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.link.available = False
    interaction = scene.who(VOICE)

    await scene.cog.play_song(interaction.as_interaction(), "never gonna")

    assert interaction.sent == [("edit_original_response", {"content": text("node-unavailable")})]
    assert scene.link.connects == []


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Play queues songs and starts them"
)
async def test_full_history(scene: Scene) -> None:
    """Requirement: Play queues songs and starts them."""
    scene.answer(PLAYLIST, LoadKind.PLAYLIST, *(song(number) for number in range(241)))
    scene.answer("ytsearch:more", LoadKind.SEARCH, song(999))
    truncated = scene.who(VOICE)
    full = scene.who(VOICE)

    await scene.cog.play_song(truncated.as_interaction(), PLAYLIST)
    await scene.cog.play_song(full.as_interaction(), "more")

    assert panel(truncated)["content"] == text("queue-truncated", added=240, refused=1)
    assert title(panel(truncated)) == "Song 0"
    assert full.sent == [("edit_original_response", {"content": text("queue-full")})]
