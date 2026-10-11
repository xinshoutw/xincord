"""The panels: edited every 5 seconds with the current song, deleted 60 seconds after their last
interaction, one per member.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

from discord_fakes import FakeInteraction, embed_dict, not_found
from music_fakes import Clock, text
from plugin_fakes import until
from xincord.plugins.music_player.panels import Panel, Panels
from xincord.plugins.music_player.replies import Screen

if TYPE_CHECKING:
    import pytest

    from conftest import Scene

DELETED: tuple[str, dict[str, object]] = ("delete_original_response", {})
NOW = Screen("now-playing")


def scene_panels(
    clock: Clock, refreshed: list[tuple[float, int]], *, refuse: bool = False
) -> Panels:
    """Panels on ``clock`` whose refresh records the time and the panel's message."""

    async def refresh(panel: Panel) -> bool:
        refreshed.append((clock.time, panel.message_id))
        return not refuse

    panels = Panels(refresh)
    panels.sleep = clock.sleep
    panels.clock = clock.monotonic
    return panels


def response(message: int = 43) -> FakeInteraction:
    """A command's response, a panel with message ``message``."""
    interaction = FakeInteraction(data={})
    interaction.original.id = message
    return interaction


def deleted(interaction: FakeInteraction) -> bool:
    """Whether the panel was deleted through ``interaction``."""
    return DELETED in interaction.sent


async def test_refresh_and_expiry() -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()
    refreshed: list[tuple[float, int]] = []
    panels = scene_panels(clock, refreshed)
    interaction = response()

    await panels.open(1, 10, 43, NOW, interaction.as_interaction())
    for _ in range(11):
        await clock.asleep(1)
        await clock.advance(5)
    await clock.asleep(1)
    await clock.advance(5)  # 60 seconds after the command
    await until(lambda: deleted(interaction))

    # 12 edits at 5 s intervals (the command's and 11), then the deletion.
    assert refreshed == [(1000.0 + 5 * step, 43) for step in range(1, 12)]
    assert set(clock.waits) == {5.0}
    assert panels.panels == {}


async def test_a_press_extends_the_panel() -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()
    refreshed: list[tuple[float, int]] = []
    panels = scene_panels(clock, refreshed)
    command, press = response(), response()

    await panels.open(1, 10, 43, NOW, command.as_interaction())
    for _ in range(10):
        await clock.asleep(1)
        await clock.advance(5)
    touched = panels.touch(43, press.as_interaction())  # at 50 seconds
    for _ in range(11):
        await clock.asleep(1)
        await clock.advance(5)  # 105 seconds: 55 after the press
    alive = not deleted(press)
    await clock.asleep(1)
    await clock.advance(5)  # 60 seconds after the press
    await until(lambda: deleted(press))

    assert touched is True
    assert alive
    assert not deleted(command)  # the press's interaction edits and deletes it now
    assert panels.touch(44, press.as_interaction()) is False  # no such panel


async def test_one_panel_per_member() -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()
    refreshed: list[tuple[float, int]] = []
    panels = scene_panels(clock, refreshed)
    first, second, other = response(43), response(44), response(45)

    await panels.open(1, 10, 43, NOW, first.as_interaction())
    await clock.asleep(1)
    await panels.open(1, 11, 44, NOW, second.as_interaction())  # the same member, another guild
    await panels.open(2, 10, 45, NOW, other.as_interaction())
    await clock.asleep(2)
    await clock.advance(5)
    await clock.asleep(2)

    assert deleted(first)
    assert sorted(message for _, message in refreshed) == [44, 45]
    assert sorted(panels.panels) == [1, 2]


async def test_refused_edits_and_close() -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()
    refreshed: list[tuple[float, int]] = []
    refusing = scene_panels(clock, refreshed, refuse=True)
    panels = scene_panels(clock, refreshed)
    dismissed, unloaded = response(43), response(44)

    await refusing.open(1, 10, 43, NOW, dismissed.as_interaction())
    await panels.open(2, 10, 44, NOW, unloaded.as_interaction())
    await clock.asleep(2)
    await clock.advance(5)
    await until(lambda: refusing.panels == {})
    await panels.close()

    assert sorted(refreshed) == [(1005.0, 43), (1005.0, 44)]
    assert (deleted(dismissed), deleted(unloaded)) == (False, False)
    assert panels.panels == {}
    assert clock.under_way() == 0


async def test_close_a_guild_and_forget() -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()
    refreshed: list[tuple[float, int]] = []
    panels = scene_panels(clock, refreshed)
    here, gone, elsewhere = response(43), response(44), response(45)
    gone.delete_error = not_found()  # deleting it fails: the member dismissed it

    await panels.open(1, 10, 43, NOW, here.as_interaction())
    await panels.open(2, 10, 44, NOW, gone.as_interaction())
    await panels.open(3, 11, 45, NOW, elsewhere.as_interaction())
    await clock.asleep(3)
    panels.forget(45)
    await panels.close_guild(10)

    assert deleted(here)
    assert panels.panels == {}
    assert not deleted(elsewhere)
    assert clock.under_way() == 0


async def test_panels_follow_the_song(scene: Scene) -> None:
    """Requirement: Panels refresh themselves and expire."""
    await scene.playing(1, 2)
    interaction = scene.who()

    await scene.cog.now_playing(interaction.as_interaction())
    assert 1 in scene.cog.panels.panels  # tracked
    await scene.clock.asleep(1)
    await scene.cog.session(10).skip()
    await scene.clock.advance(5)
    await scene.clock.asleep(1)

    method, fields = interaction.sent[-1]
    assert method == "edit_original_response"
    assert embed_dict(cast("list[Any]", fields["embeds"])[0])["title"] == "Song 2"


async def test_idle_and_stopped_players(scene: Scene) -> None:
    """Requirement: Panels refresh themselves and expire."""
    await scene.playing(1)
    interaction = scene.who()
    await scene.cog.now_playing(interaction.as_interaction())
    assert 1 in scene.cog.panels.panels
    await scene.clock.asleep(1)
    await scene.cog.session(10).stop()  # nothing plays

    await scene.clock.advance(5)
    await scene.clock.asleep(1)
    edits = len(interaction.sent)
    await scene.cog.leave_voice(scene.who().as_interaction())
    await until(lambda: deleted(interaction))

    assert edits == 1  # the command's panel only: no refresh while nothing plays
    assert scene.cog.panels.panels == {}


async def test_queue_panel_refresh(scene: Scene) -> None:
    """Requirement: Panels refresh themselves and expire."""
    await scene.playing(1, 2, 3)
    interaction = scene.who()
    await scene.cog.show_queue(interaction.as_interaction())
    assert 1 in scene.cog.panels.panels
    await scene.clock.asleep(1)

    await scene.cog.session(10).skip()
    await scene.clock.advance(5)
    await scene.clock.asleep(1)
    after_skip = [
        embed_dict(embed) for embed in cast("list[Any]", interaction.sent[-1][1]["embeds"])
    ]
    await scene.cog.session(10).skip()
    await scene.clock.advance(5)
    await scene.clock.asleep(1)
    empty = [embed_dict(embed) for embed in cast("list[Any]", interaction.sent[-1][1]["embeds"])]

    assert after_skip[0]["title"] == "Song 2"  # the refresh renders the queue
    assert after_skip[1]["fields"][0]["value"] == "1. **Song 3** | Band 3 `[03:34]`"
    assert empty[1]["description"] == text("empty-playlist")


async def test_a_failing_refresh(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()

    async def refresh(panel: Panel) -> bool:
        msg = f"cannot render panel {panel.message_id}"
        raise RuntimeError(msg)

    panels = Panels(refresh)
    panels.sleep = clock.sleep
    panels.clock = clock.monotonic
    other = response(44)
    await panels.open(2, 10, 44, NOW, other.as_interaction())
    await panels.open(1, 10, 43, NOW, response().as_interaction())
    await clock.asleep(2)
    assert panels.touch(43, other.as_interaction()) is True  # found after another panel

    with caplog.at_level(logging.ERROR):
        await clock.advance(5)
        await until(lambda: "a panel stopped refreshing" in caplog.text)

    assert "cannot render panel 43" in caplog.text
    assert panels.panels == {}


async def test_a_refused_refresh(scene: Scene) -> None:
    """Requirement: Panels refresh themselves and expire."""
    await scene.playing(1)
    interaction = scene.who()
    interaction.edit_errors = [None, not_found()]  # the member dismissed the panel
    await scene.cog.now_playing(interaction.as_interaction())
    await scene.clock.asleep(1)

    await scene.clock.advance(5)
    await until(lambda: scene.cog.panels.panels == {})

    assert scene.clock.under_way() == 0


async def test_two_panels_at_once() -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()
    panels = scene_panels(clock, [])
    old, first, second = response(43), response(44), response(45)
    await panels.open(1, 10, 43, NOW, old.as_interaction())
    old.delete_gate = asyncio.Event()  # Discord is slow to delete the member's old panel
    opening = asyncio.create_task(panels.open(1, 10, 44, NOW, first.as_interaction()))
    await until(lambda: deleted(old))

    await panels.open(1, 10, 45, NOW, second.as_interaction())  # the member's next command
    old.delete_gate.set()
    await opening

    assert panels.panels[1].message_id == 45
    assert deleted(first)
    await panels.close()
    assert clock.under_way() == 0


async def test_a_panel_after_the_unload() -> None:
    """Requirement: Panels refresh themselves and expire."""
    clock = Clock()
    panels = scene_panels(clock, [])
    await panels.close()

    await panels.open(1, 10, 43, NOW, response(43).as_interaction())  # a command that outlived it

    assert panels.panels == {}
