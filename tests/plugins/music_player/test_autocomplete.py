"""The ``query`` and ``level`` options' suggestions."""

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
from discord import app_commands

from music_fakes import song, text
from xincord.plugins.music_player.audio import LoadKind

if TYPE_CHECKING:
    from conftest import Scene

SEARCH = "ytsearch:never gonna"


def choices(found: list[app_commands.Choice[str]]) -> list[tuple[str, str]]:
    """The suggestions' names and values."""
    return [(choice.name, choice.value) for choice in found]


async def test_song_suggestions(scene: Scene) -> None:
    """Requirement: Autocomplete suggests songs and the current volume."""
    long_link = "https://www.youtube.com/watch?v=" + "x" * 80
    scene.answer(
        SEARCH,
        LoadKind.SEARCH,
        song(1, title="T" * 120),
        song(2, uri=None),  # no link to play
        song(3, uri=long_link),  # Discord refuses values over 100 characters
        *(song(number) for number in range(4, 20)),
    )
    interaction = scene.who().as_interaction()

    short = await scene.cog.song_choices(interaction, "n")
    first = await scene.cog.song_choices(interaction, "never gonna")
    again = await scene.cog.song_choices(interaction, "never gonna")

    assert short == []  # v3's two characters
    assert scene.link.loads == [SEARCH]  # the second time came from the cache
    expected = [("T" * 100, "https://www.youtube.com/watch?v=video1")] + [
        (f"Song {number} | Band {number}", f"https://www.youtube.com/watch?v=video{number}")
        for number in range(4, 13)
    ]
    assert choices(first) == expected  # ten, as v3
    assert choices(again) == expected


async def test_the_cache_keeps_the_latest_inputs(scene: Scene) -> None:
    """Requirement: Autocomplete suggests songs and the current volume."""
    interaction = scene.who().as_interaction()
    for number in range(101):
        scene.answer(f"ytsearch:song {number}", LoadKind.SEARCH, song(number))
        await scene.cog.song_choices(interaction, f"song {number}")

    await scene.cog.song_choices(interaction, "song 100")
    await scene.cog.song_choices(interaction, "song 0")

    assert scene.link.loads.count("ytsearch:song 100") == 1
    assert scene.link.loads.count("ytsearch:song 0") == 2  # v3's 100 inputs, the oldest out


async def test_slow_or_missing_node(scene: Scene) -> None:
    """Requirement: Autocomplete suggests songs and the current volume."""
    interaction = scene.who().as_interaction()
    scene.answer("ytsearch:broken", LoadKind.ERROR, error="This video is unavailable")
    scene.answer("ytsearch:nothing", LoadKind.EMPTY)

    broken = await scene.cog.song_choices(interaction, "broken")
    nothing = await scene.cog.song_choices(interaction, "nothing")
    await scene.cog.song_choices(interaction, "nothing")  # not cached: asked again
    scene.cog.search_deadline = 0  # Discord's 3 seconds have passed
    scene.link.gate = asyncio.Event()  # the node never answers
    slow = await scene.cog.song_choices(interaction, "slow search")
    scene.link.gate = None
    scene.link.available = False
    absent = await scene.cog.song_choices(interaction, "absent node")
    scene.cog.link = None
    before_ready = await scene.cog.song_choices(interaction, "before ready")

    assert (broken, nothing, slow, absent, before_ready) == ([], [], [], [], [])
    assert scene.link.loads.count("ytsearch:nothing") == 2


async def test_volume_suggestion(scene: Scene) -> None:
    """Requirement: Autocomplete suggests songs and the current volume."""
    english = scene.who().as_interaction()
    chinese = scene.who(locale=discord.Locale.taiwan_chinese).as_interaction()

    default = await scene.cog.volume_choices(english, "")
    await scene.cog.session(10).set_volume(70)
    changed = await scene.cog.volume_choices(chinese, "5")

    assert [(choice.name, choice.value) for choice in default] == [
        (text("current-volume", volume=40), 40)
    ]
    assert [(choice.name, choice.value) for choice in changed] == [
        (text("current-volume", "zh-TW", volume=70), 70)
    ]


async def test_through_the_command(scene: Scene) -> None:
    """Requirement: Autocomplete suggests songs and the current volume."""
    scene.answer(SEARCH, LoadKind.SEARCH, song(1))
    play = cast("app_commands.Command[Any, ..., None]", scene.bot.tree.get_command("play"))
    interaction = scene.who()

    await play._invoke_autocomplete(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        interaction.as_interaction(), "query", cast("Any", SimpleNamespace(query="never gonna"))
    )

    method, fields = interaction.sent[-1]
    assert method == "response.autocomplete"
    assert [choice.value for choice in cast("list[Any]", fields["choices"])] == [
        "https://www.youtube.com/watch?v=video1"
    ]
