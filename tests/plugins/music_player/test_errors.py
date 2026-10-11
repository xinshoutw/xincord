"""Unexpected errors: logged with their tracebacks and answered as v3 did.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:72-118
"""

import logging
from typing import TYPE_CHECKING, Any, cast

import pytest
from discord import app_commands

from music_fakes import text
from xincord.plugins.music_player.audio import NodeUnavailableError

if TYPE_CHECKING:
    from conftest import Scene

HIDDEN = """\
lavalink:
  password: "example-password"
messages:
  show_detailed_errors: false
"""


def fail(error: Exception) -> None:
    """Raise ``error``, so that it has a traceback."""
    raise error


def raised(error: Exception) -> Exception:
    """``error`` once raised, with its traceback."""
    try:
        fail(error)
    except Exception as caught:  # noqa: BLE001 - the test's own error
        return caught
    return error


def failure(scene: Scene, error: Exception) -> app_commands.CommandInvokeError:
    """``error`` raised by ``/play``'s callback, as discord.py hands it to the cog."""
    play = cast("app_commands.Command[Any, ..., None]", scene.bot.tree.get_command("play"))
    return app_commands.CommandInvokeError(play, error)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Errors are reported as v3 did")
async def test_detailed_errors(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Errors are reported as v3 did."""
    interaction = scene.who()
    error = raised(
        RuntimeError("the node said no at http://lavalink:2333/v4/sessions/s/players/10")
    )

    with caplog.at_level(logging.ERROR):
        await scene.cog.cog_app_command_error(interaction.as_interaction(), failure(scene, error))

    detail = "the node said no at http://lavalink:2333"  # URLs cut to their origin
    assert interaction.sent == [
        ("edit_original_response", {"content": text("command-error", error=detail)})
    ]
    assert "Traceback (most recent call last)" in caplog.text
    assert "RuntimeError: the node said no at http://lavalink:2333" in caplog.text
    assert "/v4/sessions" not in caplog.text


@pytest.mark.parametrize("config", [HIDDEN])
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Errors are reported as v3 did")
async def test_hidden_details(scene: Scene) -> None:
    """Requirement: Errors are reported as v3 did."""
    interaction = scene.who()

    await scene.cog.cog_app_command_error(
        interaction.as_interaction(), failure(scene, RuntimeError("boom"))
    )

    assert interaction.sent == [
        ("edit_original_response", {"content": text("command-error-hidden")})
    ]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Errors are reported as v3 did")
async def test_a_node_that_went_away(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Errors are reported as v3 did."""
    interaction = scene.who()

    with caplog.at_level(logging.ERROR):
        await scene.cog.cog_app_command_error(
            interaction.as_interaction(), failure(scene, NodeUnavailableError())
        )

    assert interaction.sent == [("edit_original_response", {"content": text("node-unavailable")})]
    assert caplog.text == ""  # an absent node is no unexpected error
