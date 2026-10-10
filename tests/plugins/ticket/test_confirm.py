"""Confirming a draft: a new panel, or a button added to the bot's message, and failures.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:219-232
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:106-142
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:164-176
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/lang/en-US/message/confirm-create.yaml:1-8
"""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import (
    BOT_USER,
    FakeChannel,
    FakeMessage,
    button_rows,
    embed_dict,
    forbidden,
)
from xincord.plugins.ticket.cog import IDS, Target
from xincord.plugins.ticket.model import Draft
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload

    from conftest import Scene
    from xincord.core.storage import JSON

DRAFT = Draft("Why?", title="Help", button_text="Open", admin_ids=(3,), category_id=30)
TARGET = 600
STORED: JSON = {"reasonTitle": "Old", "adminIds": [], "categoryId": 0}
LINK: dict[str, object] = {"type": 2, "style": 5, "url": "https://example.com", "label": "Site"}


def press(index: int) -> str:
    """The ID of a panel's button ``index``."""
    return IDS.build({"action": "press", "btn_index": str(index)})


def methods(sent: list[tuple[str, dict[str, object]]]) -> list[str]:
    """What was sent, in order."""
    return [method for method, _ in sent]


def row(*children: dict[str, object]) -> discord.Component:
    """An action row of a fetched message."""
    return discord.ActionRow(cast("ActionRowPayload", {"type": 1, "components": list(children)}))


def target(scene: Scene, components: list[discord.Component]) -> FakeMessage:
    """The bot's message ``TARGET`` with an embed, in the builder's channel."""
    message = FakeMessage(
        components=components,
        sent=scene.channel.sent,
        id=TARGET,
        author=BOT_USER,
        embeds=[discord.Embed(title="Panel")],
    )
    scene.channel.messages[TARGET] = message
    return message


@dataclass
class GatedChannel(FakeChannel):
    """A channel whose ``send`` waits for ``gate`` after setting ``sending``."""

    gate: asyncio.Event = field(default_factory=asyncio.Event)
    sending: asyncio.Event = field(default_factory=asyncio.Event)

    async def send(self, **fields: object) -> FakeMessage:
        """Wait for the gate, then send."""
        self.sending.set()
        await self.gate.wait()
        return await super().send(**fields)


async def test_posted_panel(scene: Scene) -> None:
    """Requirement: Confirming posts a new panel."""
    scene.keep(DRAFT)

    interaction = await scene.press("confirm-create")

    # v3 deleted the builder first and never acknowledged the press (B15).
    assert interaction.sent == [
        ("response.defer", {"ephemeral": False, "thinking": False}),
        ("delete_original_response", {}),
    ]
    [(method, fields)] = scene.channel.sent
    assert method == "channel.send"
    [embed] = cast("list[discord.Embed]", fields["embeds"])
    assert embed_dict(embed) == {"title": "Help", "color": 0x00FFFF}
    assert button_rows(fields["view"]) == [[("Open", press(0), 3)]]
    assert await scene.store.get(NAMESPACE, "10") == {
        "500": [{"reasonTitle": "Why?", "adminIds": [3], "categoryId": 30}]
    }
    assert scene.cog.drafts == {}


async def test_button_added_to_a_panel(scene: Scene) -> None:
    """Requirement: Confirming adds a button to the message."""
    first: dict[str, object] = {"type": 2, "style": 3, "custom_id": press(0), "label": "Old"}
    message = target(scene, [row(first), row(LINK)])
    await scene.store.put(NAMESPACE, "10", {str(TARGET): [STORED]})
    scene.keep(DRAFT, target=Target(TARGET, discord.Embed(title="Panel")))

    interaction = await scene.press("confirm-create")

    assert methods(interaction.sent) == ["response.defer", "delete_original_response"]
    [(method, fields)] = message.sent
    assert method == "message.edit"
    assert list(fields) == ["view"]  # the content and the embeds stay (v3 kept the first, B17)
    view = fields["view"]
    assert isinstance(view, discord.ui.View)
    assert view.is_finished()  # the router handles its buttons, not discord.py
    sent_rows = [
        [cast("dict[str, object]", component).get("custom_id") for component in row["components"]]
        for row in view.to_components()
    ]
    assert sent_rows == [
        [press(0), press(1)],  # the stored list's length (v3: the row's size, B6)
        [None],  # the link button's row stays (v3 dropped every row but the first, B17)
    ]
    assert await scene.store.get(NAMESPACE, "10") == {
        str(TARGET): [STORED, {"reasonTitle": "Why?", "adminIds": [3], "categoryId": 30}]
    }


async def test_button_added_to_a_message_without_rows(scene: Scene) -> None:
    """Requirement: Confirming adds a button to the message."""
    message = target(scene, [])
    scene.keep(DRAFT, target=Target(TARGET, discord.Embed(title="Panel")))

    await scene.press("confirm-create")

    [(_, fields)] = message.sent
    assert button_rows(fields["view"]) == [[("Open", press(0), 3)]]  # v3 threw


async def test_refused_post(scene: Scene) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    scene.channel.error = forbidden()
    scene.keep(DRAFT)

    interaction = await scene.press("confirm-create")

    reply = "Creating the ticket button failed: 403 Forbidden (error code: 0): Missing Permissions"
    assert interaction.sent == [
        ("response.defer", {"ephemeral": False, "thinking": False}),
        ("followup.send", {"content": reply, "ephemeral": True}),
    ]
    assert scene.session().draft == DRAFT
    assert await scene.store.get(NAMESPACE, "10") is None


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ("deleted", "Cannot find the message by id: 600"),
        ("full", "This message is full of buttons, please recreate a new message"),
    ],
)
async def test_message_changed_since(scene: Scene, change: str, error: str) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    other: dict[str, object] = {"type": 2, "style": 1, "custom_id": "other:1", "label": "x"}
    message = target(scene, [row(*([other] * (5 if change == "full" else 1)))])
    message.deleted = change == "deleted"
    scene.keep(DRAFT, target=Target(TARGET, discord.Embed(title="Panel")))

    interaction = await scene.press("confirm-create")

    reply = f"Creating the ticket button failed: {error}"
    assert interaction.sent[-1] == ("followup.send", {"content": reply, "ephemeral": True})
    assert scene.session().draft == DRAFT
    assert await scene.store.get(NAMESPACE, "10") is None


async def test_broken_document(scene: Scene) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    await scene.store.put(NAMESPACE, "10", [])  # not v3's shape
    scene.keep(DRAFT)

    interaction = await scene.press("confirm-create")

    # The post that could not be stored is deleted, as Giveaway's.
    assert methods(scene.channel.sent) == ["channel.send", "message.delete"]
    assert methods(interaction.sent)[-1] == "followup.send"
    assert scene.session().draft == DRAFT
    assert await scene.store.get(NAMESPACE, "10") == []


async def test_channel_without_messages(scene: Scene) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    scene.keep(DRAFT)
    interaction = scene.interaction(
        {
            "component_type": 2,
            "custom_id": IDS.build({"action": "create", "sub_action": "confirm-create"}),
        },
        discord.InteractionType.component,
    )
    interaction.channel = object()  # a channel that takes no messages

    await scene.cog.handle(
        interaction.as_interaction(),
        IDS.parse(IDS.build({"action": "create", "sub_action": "confirm-create"})),
    )

    reply = "Creating the ticket button failed: the channel takes no messages"
    assert interaction.sent[-1] == ("followup.send", {"content": reply, "ephemeral": True})
    assert scene.session().draft == DRAFT


async def test_double_confirmation(scene: Scene) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    channel = GatedChannel(id=5)
    scene.channel = channel
    scene.keep(DRAFT)

    first = asyncio.create_task(scene.press("confirm-create"))
    sending = asyncio.create_task(channel.sending.wait())
    done, _ = await asyncio.wait({first, sending}, return_when=asyncio.FIRST_COMPLETED)
    for task in done:
        task.result()  # a stub's error surfaces at once
    second = await scene.press("confirm-create")
    channel.gate.set()
    await first

    assert second.sent == [
        (
            "response.send_message",
            {"content": "This setup has expired; run the command again.", "ephemeral": True},
        )
    ]
    assert methods(channel.sent) == ["channel.send"]  # v3 would have posted twice


@dataclass
class BrokenChannel(FakeChannel):
    """A channel whose sends fail with ``failure``, or give messages that fail to change."""

    failure: BaseException | None = None

    async def send(self, **fields: object) -> FakeMessage:
        """Send, then fail, or return a message whose edits and deletion fail."""
        if self.failure is not None:
            raise self.failure
        message = await super().send(**fields)
        message.error = forbidden()
        return message


async def test_unexpected_failure(scene: Scene) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    scene.channel = BrokenChannel(id=5, failure=RuntimeError("bug"))
    scene.keep(DRAFT)

    with pytest.raises(RuntimeError, match="bug"):
        await scene.press("confirm-create")

    assert scene.session().draft == DRAFT  # the draft comes back; the core logs the error


async def test_undeletable_panel(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    scene.channel = BrokenChannel(id=5)
    await scene.store.put(NAMESPACE, "10", [])  # not v3's shape
    scene.keep(DRAFT)

    interaction = await scene.press("confirm-create")

    assert methods(interaction.sent)[-1] == "followup.send"
    assert "cannot delete the panel 500" in caplog.text


async def test_refused_edit(scene: Scene) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    message = target(scene, [])
    message.error = forbidden()
    scene.keep(DRAFT, target=Target(TARGET, discord.Embed(title="Panel")))

    interaction = await scene.press("confirm-create")

    reply = "Creating the ticket button failed: 403 Forbidden (error code: 0): Missing Permissions"
    assert interaction.sent[-1] == ("followup.send", {"content": reply, "ephemeral": True})
    assert await scene.store.get(NAMESPACE, "10") is None


async def test_broken_list(scene: Scene) -> None:
    """Requirement: A panel that cannot be posted keeps the builder."""
    message = target(scene, [])
    await scene.store.put(NAMESPACE, "10", {str(TARGET): {}})  # not v3's shape
    scene.keep(DRAFT, target=Target(TARGET, discord.Embed(title="Panel")))

    interaction = await scene.press("confirm-create")

    assert methods(interaction.sent)[-1] == "followup.send"
    assert message.sent == []  # nothing placed on the message
    assert scene.session().draft == DRAFT
