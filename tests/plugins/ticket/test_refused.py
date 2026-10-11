"""A change that Discord refuses keeps the draft, and how errors are shown to users."""

from typing import TYPE_CHECKING

import pytest

from discord_fakes import bad_request
from xincord.plugins.ticket.model import Draft
from xincord.plugins.ticket.texts import readable_error

if TYPE_CHECKING:
    from conftest import Scene

DRAFT = Draft("Why?", button_text="Open", button_emoji="x")
INVALID = "400 Bad Request (error code: 50035): Invalid Form Body In components: Invalid emoji"


async def test_invalid_emoji(scene: Scene) -> None:
    """Requirement: A change that Discord refuses keeps the draft."""
    scene.keep(DRAFT)
    scene.refuse_edit = bad_request("Invalid emoji")

    interaction = await scene.submit("modify-btn-text", {"btn-text": "Open", "btn-emoji": "abc"})

    # v3 kept the invalid emoji, and every later render of the builder failed silently.
    reply = f"Discord refused this change: {INVALID}"
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]
    assert scene.session().draft == DRAFT


async def test_refused_screen(scene: Scene) -> None:
    """Requirement: A change that Discord refuses keeps the draft."""
    scene.keep(DRAFT)
    scene.refuse_edit = bad_request("Invalid emoji")

    interaction = await scene.press("modify-category")

    [(method, _)] = interaction.sent
    assert method == "response.send_message"
    assert scene.session().draft == DRAFT


@pytest.mark.parametrize(
    ("error", "shown"),
    [
        (RuntimeError("first\nsecond"), "first second"),
        (RuntimeError("x" * 300), "x" * 200),
        # A character outside the BMP counts twice, as in Java's String.take.
        (RuntimeError("x" * 199 + chr(0x1F3AB)), "x" * 199),
        (RuntimeError(), "RuntimeError"),
        (
            TimeoutError("Connection timeout to host https://discord.com/api/v10/webhooks/1/t0k3n"),
            "Connection timeout to host https://discord.com",
        ),
    ],
)
def test_readable_errors(error: BaseException, shown: str) -> None:
    """Requirement: A failed archive is reported and cleans up."""
    assert readable_error(error) == shown
