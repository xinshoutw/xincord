"""``/add-ticket``: the builder of a button added to one of the bot's messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:33-51
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:29-51
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:145-154
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/lang/en-US/message/add-ticket.yaml:1-47
"""

from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import BOT_USER, FakeMessage, FakeUser, button_rows, embed_dict
from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload

    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("ticket")
TARGET = 600  # the panel that gets a button
COMMAND = discord.InteractionType.application_command
OTHER: dict[str, object] = {
    "type": 2,
    "style": 1,
    "custom_id": "other:1",
    "label": "x",
}  # another plugin's button
SELECT: dict[str, object] = {
    "type": 3,
    "custom_id": "other:2",
    "options": [{"label": "a", "value": "a"}],
    "min_values": 1,
    "max_values": 1,
}


def row(*children: dict[str, object]) -> discord.ActionRow:
    """An action row of a fetched message."""
    return discord.ActionRow(cast("ActionRowPayload", {"type": 1, "components": list(children)}))


def panel(
    scene: Scene,
    components: list[discord.Component] | None = None,
    author: object = BOT_USER,
    embeds: list[discord.Embed] | None = None,
) -> FakeMessage:
    """The message ``TARGET`` in the command's channel: by default the bot's, with an embed and
    one row of two buttons."""
    message = FakeMessage(
        components=[row(OTHER, OTHER)] if components is None else components,
        id=TARGET,
        author=author,
        embeds=[discord.Embed(title="Panel", color=0x123456)] if embeds is None else embeds,
    )
    scene.channel.messages[TARGET] = message
    return message


async def add(scene: Scene, text: str) -> FakeInteraction:
    """Administrator 7 runs ``/add-ticket`` with ``text``; the deferred response is message 44."""
    interaction = scene.interaction({"type": 1, "name": "add-ticket"}, COMMAND)
    interaction.original = FakeMessage(id=44)
    await scene.cog.add_ticket(interaction.as_interaction(), text)
    return interaction


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The add command opens the builder for a message",
)
async def test_added_buttons_draft(scene: Scene) -> None:
    """Requirement: The add command opens the builder for a message."""
    panel(scene)

    interaction = await add(scene, str(TARGET))

    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    assert embed_dict(embed) == {"title": "Panel", "color": 0x123456}  # the message's embed
    builder = GOLDEN["builder"]["add-ticket"]
    preview = (
        GOLDEN["preview"]["en-US"]["button"],
        IDS.build({"action": "create", "sub_action": "prev"}),
        3,
    )
    assert button_rows(fields["view"]) == [
        [preview],
        *(
            [
                (label, IDS.build({"action": "create", "sub_action": sub_action}), style)
                for label, sub_action, style in zip(labels, sub_actions, styles, strict=True)
            ]
            for labels, sub_actions, styles in zip(
                builder["labels"]["en-US"], builder["sub-actions"], builder["styles"], strict=True
            )
        ),
    ]
    session = scene.session()
    assert session.message_id == 44
    assert session.target is not None
    assert session.target.message_id == TARGET
    assert session.draft.reason_title == GOLDEN["preview"]["en-US"]["reason-title"]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The add command opens the builder for a message",
)
@pytest.mark.parametrize(
    ("text", "message", "reply"),
    [
        ("abc", "bot's", "The message ID must be a number: abc"),
        ("", "bot's", "The message ID must be a number: "),
        ("601", "bot's", "Cannot find the message by id: 601"),
        (str(TARGET), "another's", "Buttons can only be added to the bot's own messages."),
        (str(TARGET), "full", "This message is full of buttons, please recreate a new message"),
        (str(TARGET), "select", "This message is full of buttons, please recreate a new message"),
        (str(TARGET), "no embed", "This message has no embed, so no ticket button can be added."),
    ],
)
async def test_refused_messages(scene: Scene, text: str, message: str, reply: str) -> None:
    """Requirement: The add command opens the builder for a message."""
    match message:
        case "another's":
            panel(scene, author=FakeUser(id=3))
        case "full":
            panel(scene, components=[row(*([OTHER] * 5))])
        case "select":
            panel(scene, components=[row(SELECT)])
        case "no embed":
            panel(scene, embeds=[])
        case _:
            panel(scene)

    interaction = await add(scene, text)

    # v3 stayed "thinking" (B7, B9), stored a broken draft (B8) or failed at the confirmation.
    assert interaction.sent == [("edit_original_response", {"content": reply})]
    assert scene.cog.drafts == {}


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The add command opens the builder for a message",
)
async def test_message_without_rows(scene: Scene) -> None:
    """Requirement: The add command opens the builder for a message."""
    panel(scene, components=[])

    interaction = await add(scene, f" {TARGET} ")

    [(method, _)] = interaction.sent
    assert method == "edit_original_response"
    assert scene.session().target is not None
