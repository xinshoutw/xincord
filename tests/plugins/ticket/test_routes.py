"""Routing the panels' and the tickets' components, in v3's ID format too.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Event.kt:67-83
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:69-79
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:109-246
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/info.yaml:9
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeCategory, FakeMember, FakeMessage
from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload

    from conftest import Scene
    from discord_fakes import FakeInteraction, Sent
    from xincord.core.storage import JSON

GOLDEN = golden("ticket")
COMPONENT = discord.InteractionType.component
MODAL = discord.InteractionType.modal_submit
PANEL = 500
ROW = 901  # the control row's message in a ticket channel
CAROL = 255  # the ticket's member, written ff in v3's IDs
V3_PANEL = ("ticket@a:press;f:0",)
V3_ROW = tuple(f"ticket@a:{action};d:ff;e:500;f:0" for action in ("lock", "save", "delete"))
V3_SELECT = "ticket@a:save;b:select-channel;d:ff;e:500;f:0"
VIEW = discord.Permissions(view_channel=True).value


async def stored(scene: Scene) -> None:
    """Guild 10's panel 500 with one button, whose staff role is role 3."""
    entry: JSON = {"reasonTitle": "Why?", "adminIds": [3], "categoryId": 0}
    await scene.store.put(NAMESPACE, "10", {str(PANEL): [entry]})


def v3_message(sent: list[Sent], message_id: int, ids: tuple[str, ...]) -> FakeMessage:
    """A message as v3 sent it: one row of buttons with v3's IDs."""
    buttons = [{"type": 2, "style": 1, "custom_id": custom_id, "label": "x"} for custom_id in ids]
    payload = cast("ActionRowPayload", {"type": 1, "components": buttons})
    return FakeMessage([discord.ActionRow(payload)], sent, id=message_id)


def methods(interaction: FakeInteraction) -> list[str]:
    """What the plugin and the core sent, in order."""
    return [method for method, _ in interaction.sent]


def button_ids(view: object) -> list[str | None]:
    """The IDs of the buttons in ``view``."""
    assert isinstance(view, discord.ui.View)
    return [item.custom_id for item in view.children if isinstance(item, discord.ui.Button)]


def row_ids(*actions: str) -> list[str]:
    """New IDs of carol's control row for the panel's button 0."""
    fields = {"user_id": str(CAROL), "msg_id": str(PANEL), "btn_index": "0"}
    return [IDS.build({"action": action, **fields}) for action in actions]


async def test_v3_panel_button(scene: Scene) -> None:
    """Requirement: v3's panels and tickets keep working."""
    await stored(scene)
    interaction = scene.interaction(
        {"component_type": 2, "custom_id": V3_PANEL[0]}, COMPONENT, scene.who(user=8)
    )
    interaction.message = v3_message(interaction.sent, PANEL, V3_PANEL)

    await scene.bot.on_interaction(interaction.as_interaction())

    # The reason modal, then the core's upgrade of the panel it fetched.
    assert methods(interaction) == ["response.send_modal", "message.edit"]
    modal = interaction.sent[0][1]["modal"]
    assert isinstance(modal, discord.ui.Modal)
    assert modal.custom_id == IDS.build({"action": "submit", "msg_id": "500", "btn_index": "0"})
    assert button_ids(interaction.sent[1][1]["view"]) == [IDS.upgrade(V3_PANEL[0])]
    assert IDS.upgrade(V3_PANEL[0]) == "ticket:1:a=press;f=0"


async def test_v3_control_row(scene: Scene) -> None:
    """Requirement: v3's panels and tickets keep working."""
    scene.guild.members.append(FakeMember(scene.guild, id=CAROL, name="carol"))
    interaction = scene.interaction(
        {"component_type": 2, "custom_id": V3_ROW[0]}, COMPONENT, scene.who(message_id=ROW)
    )
    interaction.message = v3_message(interaction.sent, ROW, V3_ROW)

    await scene.bot.on_interaction(interaction.as_interaction())

    [(method, fields)] = scene.channel.sent
    assert method == "channel.set_permissions"
    assert fields["target"] == CAROL  # v3's hex, read as the member's ID
    overwrite = fields["overwrite"]
    assert isinstance(overwrite, discord.PermissionOverwrite)
    assert overwrite.pair()[1].value == VIEW
    assert methods(interaction) == ["response.defer", "edit_original_response", "message.edit"]
    # The unlock row in the new format; the core upgrades the row it fetched, which the fake
    # still holds with v3's IDs.
    assert button_ids(interaction.sent[1][1]["view"]) == row_ids("unlock", "save", "delete")
    assert button_ids(interaction.sent[2][1]["view"]) == row_ids("lock", "save", "delete")


async def test_v3_reason_modal(scene: Scene) -> None:
    """Requirement: v3's panels and tickets keep working."""
    await stored(scene)
    category = FakeCategory(id=30)
    scene.channel.category = category
    reason = {"type": 4, "id": 2, "custom_id": "reason", "value": "help me"}
    label = {"type": 18, "id": 1, "component": reason}
    data = {"custom_id": "ticket@a:submit;e:500;f:0", "components": [label]}
    interaction = scene.interaction(data, MODAL, scene.who(user=8, admin=False))

    await scene.bot.on_interaction(interaction.as_interaction())

    assert methods(interaction) == ["response.defer", "edit_original_response"]
    assert [method for method, _ in category.sent] == [
        "category.create_text_channel",
        "channel.send",
    ]


async def test_v3_save_select(scene: Scene) -> None:
    """Requirement: v3's panels and tickets keep working."""
    await stored(scene)
    data = {"component_type": 8, "custom_id": V3_SELECT, "values": ["6"]}
    interaction = scene.interaction(data, COMPONENT, scene.who(user=8, admin=False))
    select = FakeMessage(sent=interaction.sent, id=902)
    select.flags.ephemeral = True  # the core does not upgrade ephemeral messages
    interaction.message = select

    await scene.bot.on_interaction(interaction.as_interaction())

    reply = "Only administrators can use this."
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]


async def test_new_ids(scene: Scene) -> None:
    """Requirement: v3's panels and tickets keep working."""
    scene.guild.members.append(FakeMember(scene.guild, id=CAROL, name="carol"))
    [custom_id, *_] = row_ids("lock")
    interaction = scene.interaction(
        {"component_type": 2, "custom_id": custom_id}, COMPONENT, scene.who(message_id=ROW)
    )

    await scene.bot.on_interaction(interaction.as_interaction())

    assert methods(interaction) == ["response.defer", "edit_original_response"]


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        (COMPONENT, {"component_type": 2, "custom_id": "ticket@a:other;f:0"}),
        (COMPONENT, {"component_type": 2, "custom_id": "ticket@f:0"}),
        (COMPONENT, {"component_type": 3, "custom_id": V3_SELECT}),
        (COMPONENT, {"component_type": 5, "custom_id": V3_ROW[0]}),
        (MODAL, {"custom_id": "ticket@a:other;e:500;f:0", "components": []}),
    ],
    ids=["other-button", "before-actions", "string-select", "user-select", "other-modal"],
)
async def test_other_components(
    scene: Scene, kind: discord.InteractionType, data: dict[str, object]
) -> None:
    """Requirement: v3's panels and tickets keep working."""
    await stored(scene)
    interaction = scene.interaction(data, kind, scene.who(user=8))
    interaction.message = v3_message(interaction.sent, PANEL, V3_PANEL)

    await scene.bot.on_interaction(interaction.as_interaction())

    # No answer, as in v3; the core still upgrades the message's IDs.
    assert methods(interaction) == ["message.edit"]


async def test_malformed_v3_id(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: v3's panels and tickets keep working."""
    custom_id = "ticket@a:lock;d:zz;e:500;f:0"  # zz is no hex
    interaction = scene.interaction({"component_type": 2, "custom_id": custom_id}, COMPONENT)

    with caplog.at_level(logging.ERROR):
        await scene.bot.on_interaction(interaction.as_interaction())

    assert interaction.sent == []  # v3's parse threw before any answer
    assert f"Plugin Ticket failed to handle {custom_id}" in caplog.text
