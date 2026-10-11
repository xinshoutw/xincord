"""Pressing a panel's button asks for the reason in a modal."""

from typing import TYPE_CHECKING

import discord
import pytest

from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction
    from xincord.core.storage import JSON

GOLDEN = golden("ticket")
PANEL = 500
FIRST: JSON = {"reasonTitle": "Why?", "adminIds": [3], "categoryId": 0}
SECOND: dict[str, JSON] = {"reasonTitle": "Refund", "adminIds": [], "categoryId": 30}


async def stored(scene: Scene, reason: str = "Refund") -> None:
    """Guild 10's panel 500 with two buttons."""
    second: JSON = {**SECOND, "reasonTitle": reason}
    await scene.store.put(NAMESPACE, "10", {str(PANEL): [FIRST, second]})


def modal(interaction: FakeInteraction) -> discord.ui.Modal:
    """The modal that answered the press."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_modal"
    opened = fields["modal"]
    assert isinstance(opened, discord.ui.Modal)
    return opened


def label(opened: discord.ui.Modal) -> str | None:
    """The reason input's label."""
    [child] = opened.children
    assert isinstance(child, discord.ui.Label)
    assert isinstance(child.component, discord.ui.TextInput)
    assert child.component.custom_id == "reason"
    assert child.component.style is discord.TextStyle.paragraph
    return child.text


async def test_reason_modal(scene: Scene) -> None:
    """Requirement: Pressing a panel button asks for the reason."""
    await stored(scene)

    opened = modal(await scene.click("press", scene.who(user=8, message_id=PANEL), btn_index="1"))

    assert opened.title == "Create Ticket"
    assert label(opened) == "Refund"
    expected = IDS.build({"action": "submit", "msg_id": str(PANEL), "btn_index": "1"})
    assert opened.custom_id == expected


async def test_message_in_the_id(scene: Scene) -> None:
    """Requirement: Pressing a panel button asks for the reason."""
    await stored(scene)

    who = scene.who(user=8, message_id=999)
    opened = modal(await scene.click("press", who, msg_id=str(PANEL), btn_index="0"))

    # The modal names the message that the entry came from.
    assert label(opened) == "Why?"
    expected = IDS.build({"action": "submit", "msg_id": str(PANEL), "btn_index": "0"})
    assert opened.custom_id == expected


async def test_long_reason_title(scene: Scene) -> None:
    """Requirement: Pressing a panel button asks for the reason."""
    await stored(scene, reason="x" * 60)

    opened = modal(await scene.click("press", scene.who(user=8, message_id=PANEL), btn_index="1"))

    assert label(opened) == "x" * 45  # Discord's limit for a label


@pytest.mark.parametrize(("message", "index"), [(PANEL, "2"), (501, "0"), (PANEL, "")])
async def test_no_entry(scene: Scene, message: int, index: str) -> None:
    """Requirement: Pressing a panel button asks for the reason."""
    await stored(scene)

    interaction = await scene.click("press", scene.who(user=8, message_id=message), btn_index=index)

    reply = GOLDEN["texts"]["en-US"]["not-found"]
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]


@pytest.mark.parametrize(
    ("locale", "expected"), [("en-US", "en-US"), ("zh-TW", "zh-TW"), ("ja", "zh-TW")]
)
async def test_reply_in_the_users_locale(scene: Scene, locale: str, expected: str) -> None:
    """Requirement: Texts follow the reader."""
    who = scene.who(user=8, message_id=PANEL, locale=locale)

    interaction = await scene.click("press", who, btn_index="0")

    reply = GOLDEN["texts"][expected]["not-found"]
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]
