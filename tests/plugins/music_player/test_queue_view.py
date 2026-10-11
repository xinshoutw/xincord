"""The queue panel's list of upcoming songs: v3's lines, within Discord's limits.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:637-680
"""

import pytest

from plugin_fakes import golden
from xincord.plugins.music_player import display
from xincord.plugins.music_player.audio import STREAM_LENGTH, Track
from xincord.plugins.music_player.history import Entry, Requester

GOLDEN = golden("music_player")
ALICE = Requester(7, "Alice", "alice", "https://cdn.example/alice.png")
MORE = "and %music_player@count% more"
FIELD_LIMIT = 1024
FIELDS = 25
BUDGET = 4000


def entry(number: int, title: str | None = None, length: int = 214_000) -> Entry:
    """A song of the queue."""
    track = Track(
        f"QA{number}",
        title or f"Song {number}",
        f"Band {number}",
        None,
        str(number),
        length,
        stream=length == STREAM_LENGTH,
    )
    return Entry(track, ALICE)


def units(text: str) -> int:
    """UTF-16 code units, as Discord counts an embed's characters."""
    return len(text.encode("utf-16-le")) // 2


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The queue view fits Discord's limits"
)
def test_short_queue() -> None:
    """Requirement: The queue view fits Discord's limits."""
    entries = [entry(1), entry(2, length=STREAM_LENGTH), entry(3, length=61_000)]

    embed = display.queue_embed(entries, live_length="INFINITE", more=MORE)

    assert embed.colour is not None
    assert embed.colour.value == GOLDEN["colors"]["queue"]
    assert [(field.name, field.value, field.inline) for field in embed.fields] == [
        (
            "\N{EM DASH}",
            (
                "1. **Song 1** | Band 1 `[03:34]`\n"
                "2. **Song 2** | Band 2 `[INFINITE]`\n"
                "3. **Song 3** | Band 3 `[01:01]`"
            ),
            False,
        )
    ]


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The queue view fits Discord's limits"
)
def test_ten_lines_per_field() -> None:
    """Requirement: The queue view fits Discord's limits."""
    embed = display.queue_embed([entry(n) for n in range(1, 26)], live_length="-", more=MORE)

    lines = [field.value.split("\n") for field in embed.fields if field.value]
    assert [len(chunk) for chunk in lines] == [10, 10, 5]  # v3's chunked(10)
    assert lines[1][0].startswith("11. **Song 11**")  # the numbers go on across fields


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The queue view fits Discord's limits"
)
def test_long_queue() -> None:
    """Requirement: The queue view fits Discord's limits."""
    title = "T" * 300 + chr(0x1F3B5)  # a long title ending in a character outside the BMP
    entries = [entry(n, title) for n in range(1, 501)]

    embed = display.queue_embed(entries, live_length="-", more=MORE)

    values = [field.value or "" for field in embed.fields]
    assert all(units(value) <= FIELD_LIMIT for value in values)
    assert len(embed.fields) <= FIELDS
    assert sum(units(field.name or "") + units(field.value or "") for field in embed.fields) <= (
        BUDGET
    )
    shown = sum(value.count("\n") + 1 for value in values[:-1])
    assert values[-1] == f"and {500 - shown} more"
    assert values[0].startswith("1. **TTT")
