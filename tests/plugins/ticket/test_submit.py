"""Submitted builder modals that change the draft."""

from typing import TYPE_CHECKING

import pytest

from discord_fakes import button_rows
from xincord.plugins.ticket.model import Draft, parse_color

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

TICKET = chr(0x1F3AB)  # an admission ticket emoji
DRAFT = Draft(
    "Why?",
    author="Ticket",
    author_icon_url="https://cdn.example/icon.png",
    title="Old",
    button_text="Open",
    button_emoji="x",
)


def main_screen(interaction: FakeInteraction) -> list[list[tuple[str | None, str | None, int]]]:
    """The rows of the builder's main screen that replaced the submission's message."""
    [(method, fields)] = interaction.sent
    assert method == "response.edit_message"
    rows = button_rows(fields["view"])
    assert len(rows) == 3
    return rows


async def test_values_set(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(DRAFT)

    author = await scene.submit("modify-author", {"author": "Shop", "image": ""})
    content = await scene.submit("modify-content", {"title": "Help", "desc": "Text"})
    color = await scene.submit("modify-embed-color", {"color": "0x00ff00"})
    button = await scene.submit("modify-btn-text", {"btn-text": "Help", "btn-emoji": TICKET})
    reason = await scene.submit("modify-reason", {"reason": "What happened?"})

    for interaction in (author, content, color, reason):
        main_screen(interaction)
    assert main_screen(button)[0][0][0] == "Help"  # the preview button's new label
    assert scene.session().draft == Draft(
        "What happened?",
        author="Shop",
        title="Help",
        description="Text",
        color=0x00FF00,
        button_text="Help",
        button_emoji=TICKET,
    )


async def test_empty_reason_ignored(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(DRAFT)

    interaction = await scene.submit("modify-reason", {"reason": ""})

    main_screen(interaction)  # v3 ignored an empty reason title and showed the builder again
    assert scene.session().draft == DRAFT


@pytest.mark.parametrize(
    ("sub_action", "values", "reply"),
    [
        ("modify-embed-color", {"color": "green"}, "Invalid color; use #RRGGBB or 0xRRGGBB: green"),
        (
            "modify-embed-color",
            {"color": "#1234567"},
            "Invalid color; use #RRGGBB or 0xRRGGBB: #1234567",
        ),
        ("modify-embed-color", {"color": ""}, "Invalid color; use #RRGGBB or 0xRRGGBB: "),
        (
            "modify-btn-text",
            {"btn-text": "", "btn-emoji": ""},
            "Either ButtonText or ButtonEmoji must be provided!",
        ),
    ],
)
async def test_refused_values(
    scene: Scene, sub_action: str, values: dict[str, str], reply: str
) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(DRAFT)

    interaction = await scene.submit(sub_action, values)

    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]
    assert scene.session().draft == DRAFT


async def test_v3_zh_tw_button_modal(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(DRAFT)

    # v3's zh-TW modal, still in operators' files, named modify-btn-content (B2).
    interaction = await scene.submit("modify-btn-content", {"btn-text": "", "btn-emoji": TICKET})

    main_screen(interaction)
    assert scene.session().draft.button_text == ""
    assert scene.session().draft.button_emoji == TICKET


@pytest.mark.parametrize("sub_action", ["prev", "unknown"])
async def test_other_modals_change_nothing(scene: Scene, sub_action: str) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(DRAFT)

    interaction = await scene.submit(sub_action, {"reason": "x"})

    main_screen(interaction)  # v3 showed the builder again
    assert scene.session().draft == DRAFT


@pytest.mark.parametrize(
    ("text", "color"),
    [
        ("#00FFFF", 0x00FFFF),
        ("0x00ffff", 0x00FFFF),
        ("0X00FFFF", 0x00FFFF),
        ("00FFFF", 0x00FFFF),  # v3: 0x0FFFFF
        ("#FFF", 0x000FFF),  # v3 did not expand it either
        (" #12 ", 0x12),
        ("green", None),
        ("#1234567", None),
        ("", None),
        ("#", None),
        ("0x", None),
        ("+FF", None),
        ("#-1", None),
    ],
)
def test_colors(text: str, color: int | None) -> None:
    """Requirement: Submitted modals change the draft."""
    assert parse_color(text) == color
