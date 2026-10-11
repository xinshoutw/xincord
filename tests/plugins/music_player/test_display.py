"""What the panels show: v3's identifier rule, times, bar, thumbnails, values and queue."""

from importlib.resources import files
from pathlib import Path

import discord
import pytest

from discord_fakes import embed_dict
from plugin_fakes import golden
from xincord.core.i18n import Lang
from xincord.core.templates import Templates, render_message
from xincord.core.templates.render import EMPTY_FIELD
from xincord.plugins.music_player import display
from xincord.plugins.music_player.audio import STREAM_LENGTH, Track
from xincord.plugins.music_player.display import Look
from xincord.plugins.music_player.history import Entry, LoopMode, Requester
from xincord.plugins.music_player.ids import IDS

GOLDEN = golden("music_player")
# Each bar emoji as a short marker, so that a bar reads as text.
EMOJIS = {
    "progress_white_start": "<ws>",
    "progress_white_full": "<wf>",
    "progress_white_end": "<we>",
    "progress_black": "<b>",
    "progress_black_end": "<be>",
    "media_play": "<play>",
    "media_pause": "<pause>",
    "media_ordered": "<:ordered:1395593807352954951>",
    "media_repeat_once": "<:once:1395593807352954952>",
    "media_previous": "<:previous:1395593807352954953>",
    "media_pause_resume": "<:pause_resume:1395593807352954954>",
    "media_next": "<:next:1395593807352954955>",
    "media_disconnect": "<:disconnect:1395593807352954956>",
}
SONG = Track(
    encoded="QAAA",
    title="Never Gonna Give You Up",
    author="Rick Astley",
    uri="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    identifier="dQw4w9WgXcQ",
    length=214_000,
)
LOOK = Look(EMOJIS, live="LIVE", live_length="INFINITE")
ALICE = Requester(7, "Alice", "alice", "https://cdn.example/alice.png")


def panel_buttons(view: object) -> list[tuple[str | None, int, str]]:
    """The custom ID, the style and the emoji of each button of a rendered panel."""
    assert isinstance(view, discord.ui.View)
    found: list[tuple[str | None, int, str]] = []
    for item in view.children:
        assert isinstance(item, discord.ui.Button)
        found.append((item.custom_id, item.style.value, str(item.emoji)))
    return found


def bar(white: int, *, end: bool = False) -> str:
    """v3's BAR_ARRAY entry with ``white`` full white segments between its ends."""
    if end:
        return "<ws>" + "<wf>" * 13 + "<we>"
    return "<ws>" + "<wf>" * white + "<b>" * (13 - white) + "<be>"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("never gonna", "ytsearch:never gonna"),
        ("https://youtu.be/x", "https://youtu.be/x"),
        ("youtu.be/x", "youtu.be/x"),
        ("www.youtube.com/watch?v=x", "www.youtube.com/watch?v=x"),
        ("soundcloud.com/a/b", "soundcloud.com/a/b"),
        ("open.spotify.com/track/x", "open.spotify.com/track/x"),
        ("httpfoo", "httpfoo"),
        ("scsearch:foo", "ytsearch:scsearch:foo"),
    ],
)
def test_searches_and_links(query: str, expected: str) -> None:
    """Requirement: Queries become Lavalink identifiers as in v3."""
    # The vectors of the inventory, section 13.1.
    assert display.identifier(query) == expected


@pytest.mark.parametrize(
    ("milliseconds", "text"),
    [
        (0, "00:00"),
        (59_999, "00:59"),
        (60_000, "01:00"),
        (3_599_999, "59:59"),
        (3_600_000, "01:00:00"),
        (360_000_000, "100:00:00"),
        (-1, "00:00"),
    ],
)
def test_times(milliseconds: int, text: str) -> None:
    """Requirement: Panels show v3's track layout."""
    assert display.format_time(milliseconds) == text


def test_lengths() -> None:
    """Requirement: Panels show v3's track layout."""
    stream = Track("QAAB", "Radio", "Station", None, "radio", STREAM_LENGTH, stream=True)

    assert display.length_text(SONG, "INFINITE") == "03:34"
    assert display.length_text(stream, "INFINITE") == "INFINITE"  # v3's formatTime(MAX_VALUE)


@pytest.mark.parametrize(
    ("position", "white", "end"),
    [
        pytest.param(0, 0, False, id="start"),
        pytest.param(107_000, 7, False, id="half"),
        pytest.param(214_000, 13, True, id="end"),
        pytest.param(300_000, 13, True, id="past the end"),
        pytest.param(-5, 0, False, id="negative"),
    ],
)
def test_progress_bar(position: int, white: int, *, end: bool) -> None:
    """Requirement: Panels show v3's track layout."""
    expected = (
        f"<play> {display.format_time(max(position, 0))}{bar(white, end=end)}03:34"
        if position >= 0
        else f"<play> 00:00{bar(0)}03:34"
    )

    assert display.progress_bar(position, SONG, playing=True, look=LOOK) == (expected)


def test_streams_and_paused_songs() -> None:
    """Requirement: Panels show v3's track layout."""
    stream = Track("QAAB", "Radio", "Station", None, "radio", STREAM_LENGTH, stream=True)
    empty = Track("QAAC", "Silence", "Nobody", None, "silence", 0)

    assert display.progress_bar(0, stream, playing=True, look=LOOK) == ("<play> LIVE")
    assert display.progress_bar(0, empty, playing=False, look=LOOK) == ("<pause> LIVE")
    assert display.progress_bar(0, SONG, playing=False, look=LOOK).startswith("<pause> 00:00<ws>")


@pytest.mark.parametrize(
    ("url", "video"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/abc_-1?t=3", "abc_-1"),
        ("https://www.youtube.com/embed/xyz", "xyz"),
        ("https://youtube.com/v/xyz", "xyz"),
        ("https://youtube.com.br/watch?v=id", "id"),
        ("https://www.youtube.com/watch?feature=a&v=id", None),
        ("https://soundcloud.com/a/b", None),
    ],
)
def test_youtube_ids(url: str, video: str | None) -> None:
    """Requirement: Panels show v3's track layout."""
    # The vectors of the inventory, section 13.5.
    assert display.youtube_id(url) == video


def test_thumbnails() -> None:
    """Requirement: Panels show v3's track layout."""
    artwork = Track(
        "QAAD",
        "Song",
        "Band",
        "https://soundcloud.com/a/b",
        "b",
        1000,
        artwork_url="https://i1.sndcdn.com/artworks-x.jpg",
    )
    feature = Track(
        "QAAE", "Song", "Band", "https://www.youtube.com/watch?feature=a&v=id", "id", 1000
    )
    other = Track("QAAF", "Song", "Band", "https://soundcloud.com/a/c", "c", 1000)

    assert display.thumbnail(artwork) == "https://i1.sndcdn.com/artworks-x.jpg"
    assert display.thumbnail(SONG) == "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
    # v3 fell back to the node's identifier when its patterns found no video ID.
    assert display.thumbnail(feature) == "https://img.youtube.com/vi/id/maxresdefault.jpg"
    assert display.thumbnail(other) == "https://i.meee.com.tw/GHexAW6.png"  # v3's default


def test_track_values() -> None:
    """Requirement: Panels show v3's track layout."""
    entry = Entry(SONG, ALICE)

    playing = display.track_values(
        entry,
        position=107_000,
        playing=True,
        loop=LoopMode.SEQUENTIAL,
        look=LOOK,
    )
    paused = display.track_values(entry, position=0, playing=False, loop=LoopMode.SINGLE, look=LOOK)

    assert playing == {
        "music_player@song_author_name": "Rick Astley",
        "music_player@song_name": "Never Gonna Give You Up",
        "music_player@song_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "music_player@song_thumbnail_url": (
            "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
        ),
        "music_player@track_duration": "03:34",
        "music_player@song_duration": f"<play> 01:47{bar(7)}03:34",
        "music_player@song_requester_username": "alice",
        "music_player@song_requester_name": "Alice",
        "music_player@song_requester_avatar_url": "https://cdn.example/alice.png",
        "music_player@song_requester_id": "7",
        "music_player@player_current_color": "0x68c06e",
        "music_player@player_currnet_loop_mode_emoji": "<:ordered:1395593807352954951>",
    }
    assert paused["music_player@player_current_color"] == "0xba9c55"
    assert paused["music_player@player_currnet_loop_mode_emoji"] == "<:once:1395593807352954952>"
    assert paused["music_player@song_duration"].startswith("<pause> 00:00")
    assert display.emoji_values(EMOJIS) == {
        "music_player@media_previous_emoji": "<:previous:1395593807352954953>",
        "music_player@media_pause_resume_emoji": "<:pause_resume:1395593807352954954>",
        "music_player@media_next_emoji": "<:next:1395593807352954955>",
        "music_player@media_disconnect_emoji": "<:disconnect:1395593807352954956>",
    }


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_golden_panels(locale: str) -> None:
    """Requirement: Panels show v3's track layout."""
    lang = Lang.load(
        "MusicPlayer", Path(str(files("xincord.plugins.music_player") / "lang")), "zh-TW"
    )
    templates = Templates.load(lang)
    values = (
        display.track_values(
            Entry(SONG, ALICE),
            position=0,
            playing=True,
            loop=LoopMode.SEQUENTIAL,
            look=LOOK,
        )
        | display.emoji_values(EMOJIS)
        | {"music_player@player_volume_before": "40", "music_player@player_volume_after": "70"}
    )

    play = render_message(templates.message("play", locale), values, build_id=IDS.build)
    volume = render_message(templates.message("volume", locale), values, build_id=IDS.build)

    embed = embed_dict(play.embeds[0])
    assert embed["footer"] == {
        "text": GOLDEN["footer"][locale],
        "icon_url": "https://cdn.example/alice.png",
    }
    assert embed["color"] == GOLDEN["colors"]["playing"]
    assert embed["title"] == "Never Gonna Give You Up"
    assert embed["author"] == {"name": "Rick Astley"}
    assert embed["fields"] == [
        {"name": EMPTY_FIELD, "value": values["music_player@song_duration"], "inline": False}
    ]
    assert embed["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert embed["thumbnail"] == {"url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"}
    assert panel_buttons(play.view) == [
        (f"music_player:1:a={action}", style, EMOJIS[emoji])
        for (style, action), emoji in zip(
            GOLDEN["buttons"],
            (
                "media_previous",
                "media_pause_resume",
                "media_next",
                "media_ordered",
                "media_disconnect",
            ),
            strict=True,
        )
    ]
    assert embed_dict(volume.embeds[0]) == {
        "title": GOLDEN["volume_title"][locale],
        "color": GOLDEN["colors"]["volume"],
    }
    assert volume.view is None
