"""Selections in the builder: staff roles, the category and the button's color."""

from typing import TYPE_CHECKING

import discord
import pytest

from discord_fakes import FakeChannel, button_rows
from xincord.plugins.ticket.model import Draft

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

ROLE_SELECT = 6
CATEGORY = 30
DRAFT = Draft("Why?", admin_ids=(1,), category_id=0)


def main_screen(interaction: FakeInteraction) -> list[list[tuple[str | None, str | None, int]]]:
    """The rows of the builder's main screen that replaced the selection's message."""
    [(method, fields)] = interaction.sent
    assert method == "response.edit_message"
    rows = button_rows(fields["view"])
    assert len(rows) == 3
    return rows


def categories(scene: Scene) -> None:
    """Guild 10 caches the category 30 and the text channel 32."""
    scene.guild.channels.extend(
        [
            FakeChannel(id=CATEGORY, type=discord.ChannelType.category),
            FakeChannel(id=32, type=discord.ChannelType.text),
        ]
    )


async def test_roles_category_and_style(scene: Scene) -> None:
    """Requirement: Selections change the draft."""
    categories(scene)
    scene.keep(DRAFT)

    roles = await scene.choose("modify-admin", ["3", "4"], component_type=ROLE_SELECT)
    category = await scene.choose("modify-category", [str(CATEGORY)])
    style = await scene.press("modify-btn-color-submit", color_index="4")

    main_screen(roles)
    main_screen(category)
    assert main_screen(style)[0][0][2] == 4  # the preview button is red
    assert scene.session().draft == Draft(
        "Why?", admin_ids=(3, 4), category_id=CATEGORY, button_style=4
    )


@pytest.mark.parametrize("channel", ["31", "32", "x"])
async def test_unknown_category(scene: Scene, channel: str) -> None:
    """Requirement: Selections change the draft."""
    categories(scene)
    scene.keep(DRAFT)

    interaction = await scene.choose("modify-category", [channel])

    reply = f"Cannot find a category with the id {channel}!"  # v3's text
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]
    assert scene.session().draft == DRAFT


@pytest.mark.parametrize("index", ["0", "5", "x", ""])
async def test_other_styles_change_nothing(scene: Scene, index: str) -> None:
    """Requirement: Selections change the draft."""
    scene.keep(DRAFT)

    interaction = await scene.press("modify-btn-color-submit", color_index=index)

    # v3's ButtonStyle.fromKey gave no usable style there, and the press failed.
    main_screen(interaction)
    assert scene.session().draft == DRAFT


async def test_other_selects_change_nothing(scene: Scene) -> None:
    """Requirement: Selections change the draft."""
    scene.keep(DRAFT)

    interaction = await scene.choose("other", ["3"], component_type=ROLE_SELECT)

    main_screen(interaction)  # v3 showed the builder again
    assert scene.session().draft == DRAFT
