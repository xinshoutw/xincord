"""Routing the builder's and the post's components, in the legacy ID format too."""

from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeMessage
from plugin_fakes import golden
from xincord.plugins.giveaway.cog import IDS
from xincord.plugins.giveaway.model import Draft, Instance, Prize

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload

    from conftest import Scene
    from discord_fakes import FakeInteraction, Sent

GOLDEN = golden("giveaway")
NOW = 1772244000  # the tests' clock
GIVEAWAY = Instance(
    id="3f2a9c1b7e4d4a60",
    guild_id=10,
    channel_id=5,
    message_id=500,
    creator_id=7,
    config=Draft(title="Nitro", end_at=NOW + 3600, prizes=(Prize("Nitro", 1),)),
    locale_tag="en-US",
)
# The post's buttons with legacy IDs.
LEGACY_POST = (
    "giveaway@a:participate;c:{id}",
    "giveaway@a:draw;c:{id}",
    "giveaway@a:reroll;c:{id}",
)
COMPONENT = discord.InteractionType.component
MODAL = discord.InteractionType.modal_submit


def legacy_post(sent: list[Sent], ids: tuple[str, ...] = LEGACY_POST) -> FakeMessage:
    """Giveaway 3f2a9c1b7e4d4a60's post: three buttons with legacy IDs."""
    buttons = [
        {"type": 2, "style": 1, "custom_id": custom_id.format(id=GIVEAWAY.id), "label": "x"}
        for custom_id in ids
    ]
    payload = cast("ActionRowPayload", {"type": 1, "components": buttons})
    return FakeMessage([discord.ActionRow(payload)], sent, id=500)


def methods(interaction: FakeInteraction) -> list[str]:
    """What the plugin and the core sent, in order."""
    return [method for method, _ in interaction.sent]


def button_ids(view: object) -> list[str | None]:
    """The IDs of the buttons in ``view``."""
    assert isinstance(view, discord.ui.View)
    return [item.custom_id for item in view.children if isinstance(item, discord.ui.Button)]


async def test_legacy_post(scene: Scene) -> None:
    """Requirement: Legacy posts keep working."""
    await scene.add(GIVEAWAY)
    custom_id = LEGACY_POST[0].format(id=GIVEAWAY.id)
    interaction = scene.interaction(
        {"component_type": 2, "custom_id": custom_id}, COMPONENT, scene.who(user=8, admin=False)
    )
    interaction.message = legacy_post(interaction.sent)

    await scene.bot.on_interaction(interaction.as_interaction())

    assert (await scene.stored(GIVEAWAY.id)).participant_ids == (8,)
    # The press showed the post with new IDs; the core then upgrades the message it fetched (here
    # the fake, which still holds the legacy IDs).
    assert methods(interaction) == [
        "response.defer",
        "edit_original_response",
        "followup.send",
        "message.edit",
    ]
    expected = [
        f"giveaway:1:a={action};c={GIVEAWAY.id}" for action in ("participate", "draw", "reroll")
    ]
    assert button_ids(interaction.sent[1][1]["view"]) == expected
    assert button_ids(interaction.sent[3][1]["view"]) == expected
    assert IDS.upgrade(custom_id) == expected[0]


@pytest.mark.parametrize("kind", [COMPONENT, MODAL])
async def test_legacy_builder(scene: Scene, kind: discord.InteractionType) -> None:
    """Requirement: Legacy posts keep working."""
    custom_id = "giveaway@a:create;b:set-title"  # a legacy builder: no draft
    data: dict[str, object] = {"custom_id": custom_id, "components": []}
    if kind is COMPONENT:
        data["component_type"] = 2
    interaction = scene.interaction(data, kind)
    builder = FakeMessage(sent=interaction.sent, id=43)
    builder.flags.ephemeral = True  # the core does not upgrade ephemeral messages
    interaction.message = builder

    await scene.bot.on_interaction(interaction.as_interaction())

    reply = GOLDEN["replies"]["en-US"]["expired"]
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]


async def test_new_ids(scene: Scene) -> None:
    """Requirement: Legacy posts keep working."""
    await scene.add(GIVEAWAY)
    custom_id = IDS.build({"action": "participate", "giveaway_id": GIVEAWAY.id})
    interaction = scene.interaction(
        {"component_type": 2, "custom_id": custom_id}, COMPONENT, scene.who(user=8, message_id=500)
    )

    await scene.bot.on_interaction(interaction.as_interaction())

    assert methods(interaction) == ["response.defer", "edit_original_response", "followup.send"]


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        (COMPONENT, {"component_type": 2, "custom_id": "giveaway:1:a=other"}),
        (COMPONENT, {"component_type": 2, "custom_id": "giveaway@a:other;c:x"}),
        (COMPONENT, {"component_type": 3, "custom_id": "giveaway:1:a=create;b=set-title"}),
        (COMPONENT, {"component_type": 5, "custom_id": "giveaway:1:a=participate;c=x"}),
        (MODAL, {"custom_id": "giveaway:1:a=draw;c=x", "components": []}),
        (COMPONENT, {"component_type": 2, "custom_id": "giveaway@a:participate;x"}),
    ],
    ids=["other", "legacy-other", "string-select", "user-select", "modal-draw", "malformed"],
)
async def test_other_actions(
    scene: Scene, kind: discord.InteractionType, data: dict[str, object]
) -> None:
    """Requirement: Legacy posts keep working."""
    scene.keep(Draft(title="Nitro"))
    interaction = scene.interaction(data, kind)

    await scene.bot.on_interaction(interaction.as_interaction())

    assert interaction.sent == []
    assert scene.draft() == Draft(title="Nitro")
