"""Builder buttons that switch the builder's screen, through the press."""

from typing import TYPE_CHECKING, cast

import discord

from discord_fakes import button_rows, embed_dict
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.model import Draft

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

DRAFT = Draft("Why?", title="Help", button_text="Open")
PREVIEW = ("Open", IDS.build({"action": "create", "sub_action": "prev"}), 3)
BACK = ("Back", IDS.build({"action": "create", "sub_action": "back"}), 2)


def builder(interaction: FakeInteraction) -> tuple[list[discord.Embed], discord.ui.View]:
    """The builder that replaced the press's message."""
    [(method, fields)] = interaction.sent
    assert method == "response.edit_message"
    assert fields["content"] == ""
    view = fields["view"]
    assert isinstance(view, discord.ui.View)
    return list(cast("tuple[discord.Embed, ...]", fields["embeds"])), view


def items(view: discord.ui.View) -> list[tuple[str, str | None, int | None]]:
    """Each component's kind, ID and row."""
    return [
        (type(item).__name__, getattr(item, "custom_id", None), item.row) for item in view.children
    ]


async def test_category_screen_and_back(scene: Scene) -> None:
    """Requirement: Builder buttons switch screens."""
    scene.keep(DRAFT)

    embeds, view = builder(await scene.press("modify-category"))

    assert [embed_dict(embed) for embed in embeds] == [{"title": "Help", "color": 0x00FFFF}]
    select_id = IDS.build({"action": "create", "sub_action": "modify-category"})
    assert items(view) == [
        ("Button", PREVIEW[1], 0),
        ("ChannelSelect", select_id, 1),
        ("Button", BACK[1], 2),
    ]
    select = view.children[1]
    assert isinstance(select, discord.ui.ChannelSelect)
    assert select.channel_types == [discord.ChannelType.category]
    assert (select.min_values, select.max_values) == (1, 1)
    assert select.placeholder == "Empty here to by default"

    _, main = builder(await scene.press("back"))

    assert button_rows(main)[0] == [PREVIEW]
    assert len(button_rows(main)) == 3  # the main screen's rows
    assert scene.session().draft == DRAFT


async def test_role_screen(scene: Scene) -> None:
    """Requirement: Builder buttons switch screens."""
    scene.keep(DRAFT)

    _, view = builder(await scene.press("modify-admin"))

    select_id = IDS.build({"action": "create", "sub_action": "modify-admin"})
    assert items(view) == [
        ("Button", PREVIEW[1], 0),
        ("RoleSelect", select_id, 1),
        ("Button", BACK[1], 2),
    ]
    select = view.children[1]
    assert isinstance(select, discord.ui.RoleSelect)
    assert (select.min_values, select.max_values) == (1, 25)


async def test_color_screen(scene: Scene) -> None:
    """Requirement: Builder buttons switch screens."""
    scene.keep(DRAFT)

    _, view = builder(await scene.press("modify-btn-color"))

    colors = [
        (
            label,
            IDS.build(
                {"action": "create", "sub_action": "modify-btn-color-submit", "color_index": index}
            ),
            int(index),
        )
        for label, index in (("BLUE", "1"), ("GRAY", "2"), ("GREEN", "3"), ("RED", "4"))
    ]
    assert button_rows(view) == [[PREVIEW], colors, [BACK]]
