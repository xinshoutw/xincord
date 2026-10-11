"""The panels' five buttons: previous, pause or resume, skip, loop mode and disconnect.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:96-118
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:298-333
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:783-956
"""

from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import embed_dict
from music_fakes import text
from plugin_fakes import golden
from xincord.plugins.music_player.audio import NodeUnavailableError
from xincord.plugins.music_player.emojis import FALLBACKS
from xincord.plugins.music_player.ids import IDS

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("music_player")
VOICE = 20
PANEL = 500  # the pressed panel's message
DEFERRED: tuple[str, dict[str, object]] = (
    "response.defer",
    {"ephemeral": False, "thinking": False},
)
HIDDEN = """\
lavalink:
  password: "example-password"
messages:
  show_detailed_errors: false
"""


async def press(scene: Scene, action: str, **options: Any) -> FakeInteraction:  # noqa: ANN401
    """Press ``action`` on a panel through the cog's handler, as the core routes it."""
    interaction = scene.press(action, PANEL, **options)
    custom_id = str(interaction.data["custom_id"])
    await scene.cog.handle(interaction.as_interaction(), IDS.parse(custom_id))
    return interaction


def panel(interaction: FakeInteraction) -> dict[str, Any]:
    """The pressed panel's first embed after the press."""
    method, fields = interaction.sent[-1]
    assert method == "edit_original_response"
    return embed_dict(cast("list[Any]", fields["embeds"])[0])


def said(interaction: FakeInteraction, key: str, **values: object) -> bool:
    """Whether the press was acknowledged, then the panel's content became the text ``key``."""
    return interaction.sent == [
        DEFERRED,
        ("edit_original_response", {"content": text(key, **values)}),
    ]


async def test_v3_and_new_ids(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    player = await scene.playing(1, 2, 3)
    legacy = scene.press("skip", PANEL, legacy=True)
    current = scene.press("skip", PANEL)

    await scene.bot.on_interaction(legacy.as_interaction())
    await scene.bot.on_interaction(current.as_interaction())

    assert [legacy.sent[0], current.sent[0]] == [DEFERRED, DEFERRED]  # acknowledged at once (B3)
    assert (panel(legacy)["title"], panel(current)["title"]) == ("Song 2", "Song 3")
    assert player.played()[-2:] == [("Song 2", 2, 40), ("Song 3", 3, 40)]


async def test_member_outside_voice(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    player = await scene.playing(1, 2)

    pressed = await press(scene, "skip", channel=None)

    assert said(pressed, "button-join-voice")  # v3 never showed it (B3)
    assert player.played() == [("Song 1", 1, 40)]


async def test_previous_pause_and_loop(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    player = await scene.playing(1, 2)
    await scene.cog.session(10).skip()
    await scene.cog.session(10).pause()
    player.position = 7000

    previous = await press(scene, "previous")
    paused = await press(scene, "pause-resume")
    resumed = await press(scene, "pause-resume")
    single = await press(scene, "loop")
    sequential = await press(scene, "loop")

    assert panel(previous)["title"] == "Song 2"  # restarted after 5 seconds
    assert player.played()[-1] == ("Song 2", 3, 40)
    assert panel(paused)["color"] == GOLDEN["colors"]["paused"]
    assert panel(resumed)["color"] == GOLDEN["colors"]["playing"]
    assert [call for call in player.calls if call[0] == "pause"][-2:] == [
        ("pause", True),
        ("pause", False),
    ]
    loop_emoji = [
        str(item.emoji)
        for interaction in (single, sequential)
        for item in cast("Any", interaction.sent[-1][1]["view"]).children
        if item.custom_id == "music_player:1:a=loop"
    ]
    assert loop_emoji == [FALLBACKS["media_repeat_once"], FALLBACKS["media_ordered"]]


async def test_nothing_to_do(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    no_song = await press(scene, "previous")
    not_connected = await press(scene, "disconnect")
    nothing = await press(scene, "pause-resume")
    await scene.playing(1)
    last = await press(scene, "skip")
    await scene.cog.session(10).skip_many(1)  # the list ended: idle
    idle = await press(scene, "previous")

    assert said(no_song, "previous-no-song")
    assert said(not_connected, "not-connected")
    assert said(nothing, "nothing-playing")
    assert said(last, "no-more-songs")
    assert said(idle, "previous-idle")


async def test_disconnect(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    await scene.playing(1, 2)
    command = scene.who()
    await scene.cog.now_playing(command.as_interaction())
    message = command.original.id

    pressed = scene.press("disconnect", message)
    await scene.cog.handle(pressed.as_interaction(), IDS.parse("music_player:1:a=disconnect"))

    assert scene.link.disconnects == [10]
    assert scene.cog.sessions[10].history.entries == []
    assert pressed.sent == [DEFERRED, ("delete_original_response", {})]
    assert scene.cog.panels.panels == {}


async def test_loop_without_a_song(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    pressed = await press(scene, "loop")

    assert pressed.sent == [DEFERRED]  # acknowledged; v3 left the press unanswered
    assert scene.cog.session(10).loop.value == "single"  # v3 changed the mode anyway


async def test_unknown_action(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    pressed = await press(scene, "shuffle")

    assert pressed.sent == []


async def test_a_press_extends_the_panel(scene: Scene) -> None:
    """Requirement: Panel buttons control the guild's player."""
    await scene.playing(1, 2)
    command = scene.who()
    await scene.cog.now_playing(command.as_interaction())
    tracked = scene.cog.panels.panels[1]
    scene.clock.time += 50

    pressed = scene.press("pause-resume", command.original.id)
    await scene.cog.handle(pressed.as_interaction(), IDS.parse("music_player:1:a=pause-resume"))

    assert tracked.interaction is pressed.as_interaction()
    assert tracked.touched == scene.clock.time


@pytest.mark.parametrize("config", [HIDDEN])
async def test_hidden_details(scene: Scene) -> None:
    """Requirement: Errors are reported as v3 did."""
    player = await scene.playing(1, 2)
    player.error = RuntimeError("the node said no")

    pressed = await press(scene, "skip")

    assert said(pressed, "button-error-hidden")


@pytest.mark.parametrize(
    ("error", "key", "values"),
    [
        pytest.param(
            RuntimeError("the node said no"), "button-error", {"error": "the node said no"}
        ),
        pytest.param(NodeUnavailableError(), "node-unavailable", {}, id="absent node"),
    ],
)
async def test_detailed_button_errors(
    scene: Scene, error: Exception, key: str, values: dict[str, str]
) -> None:
    """Requirement: Errors are reported as v3 did."""
    player = await scene.playing(1, 2, 3)
    player.error = error

    pressed = await press(scene, "skip")

    assert said(pressed, key, **values)
