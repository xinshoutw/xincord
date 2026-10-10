"""Builder buttons that open pre-filled modals, and the preview button's reason modal.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:79-121
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:140-167
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:186-200
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/lang/en-US/modal/modify-author.yaml:1-20
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/lang/zh-TW/modal/modify-btn-text.yaml:1-3
"""

from typing import TYPE_CHECKING

import discord
import pytest

from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.model import Draft

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

TICKET = chr(0x1F3AB)  # an admission ticket emoji
DRAFT = Draft(
    "Why?",
    author="Shop",
    author_icon_url="https://cdn.example/icon.png",
    title="Help",
    description="Desc",
    color=0x00FF00,
    button_text="Open",
    button_emoji=TICKET,
)

type Input = tuple[str | None, str, str | None, bool, int | None]


def modal(interaction: FakeInteraction) -> discord.ui.Modal:
    """The modal that answered the press."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_modal"
    opened = fields["modal"]
    assert isinstance(opened, discord.ui.Modal)
    return opened


def inputs(opened: discord.ui.Modal) -> list[Input]:
    """Each text input's label, ID, value, whether it is required and its maximum length."""
    found: list[Input] = []
    for label in opened.children:
        assert isinstance(label, discord.ui.Label)
        text_input = label.component
        assert isinstance(text_input, discord.ui.TextInput)
        found.append(
            (
                label.text,
                text_input.custom_id,
                text_input.default,
                text_input.required,
                text_input.max_length,
            )
        )
    return found


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Builder buttons open pre-filled modals"
)
@pytest.mark.parametrize(
    ("sub_action", "expected"),
    [
        (
            "modify-author",
            [
                ("Modify author name", "author", "Shop", False, 256),
                ("Modify Author Image", "image", "https://cdn.example/icon.png", False, 4000),
            ],
        ),
        (
            "modify-content",
            [
                ("Modify title", "title", "Help", False, 256),
                ("Modify description", "desc", "Desc", False, 4000),
            ],
        ),
        ("modify-color", [("Modify color", "color", "#00FF00", True, 8)]),
        (
            "modify-btn-text",
            [
                ("Modify button text", "btn-text", "Open", False, 80),
                ("Modify button emoji", "btn-emoji", TICKET, False, None),
            ],
        ),
        ("modify-reason", [("Modify reason", "reason", "Why?", True, 45)]),
    ],
)
async def test_pre_filled_modals(scene: Scene, sub_action: str, expected: list[Input]) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(DRAFT)

    opened = modal(await scene.press(sub_action))

    assert opened.title == "Create Ticket"
    assert inputs(opened) == expected
    # v3's modal IDs: modify-color opens modify-embed-color, modify-reason modify-reason.
    names = {"modify-color": "modify-embed-color"}
    sub = names.get(sub_action, sub_action)
    assert opened.custom_id == IDS.build({"action": "create", "sub_action": sub})
    assert scene.session().draft == DRAFT


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Builder buttons open pre-filled modals"
)
async def test_empty_values(scene: Scene) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(Draft("Why?", color=0x0000AB))

    author = inputs(modal(await scene.press("modify-author")))
    color = inputs(modal(await scene.press("modify-color")))

    # An unset value leaves the input empty, as v3's empty text did.
    assert [value for _, _, value, _, _ in author] == [None, None]
    assert color[0][2] == "#0000AB"  # v3's "#%06X"


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Builder buttons open pre-filled modals"
)
async def test_zh_tw_button_modal(scene: Scene) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(DRAFT, scene.who(locale="zh-TW"))

    opened = modal(await scene.press("modify-btn-text", scene.who(locale="zh-TW")))

    # v3's zh-TW file said modify-btn-content, which the handler did not know (B2).
    assert opened.custom_id == IDS.build({"action": "create", "sub_action": "modify-btn-text"})


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="The preview shows the draft")
async def test_preview_button(scene: Scene) -> None:
    """Requirement: The preview shows the draft."""
    scene.keep(DRAFT)

    opened = modal(await scene.press("prev"))

    # v3's preview-reason, unreachable there (B1): titled with the reason title.
    assert opened.title == "Why?"
    assert inputs(opened) == [("Reason", "reason", None, True, None)]
    assert opened.custom_id == IDS.build({"action": "create", "sub_action": "prev"})
