"""Saving a ticket: the save button's channel select, and the select's checks in v3's order.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:198-242
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:312-358
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:834-852
"""

from typing import TYPE_CHECKING

import discord
import pytest

from discord_fakes import FakeChannel, FakeRole, FakeUser
from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("ticket")
GUILD = 10  # the guild, whose ID its @everyone role shares
PANEL = "500"
ROW = 901  # the control row's message in the ticket channel
FIELDS = {"user_id": "8", "msg_id": PANEL, "btn_index": "0"}
TARGET = 6  # the text channel to save the conversation in
CHOOSE = "Choose the text channel to save the conversation in"
ADMIN_ONLY = "Only administrators can use this."
NO_MEMBER = "Error (the member cannot be found)"
NOT_TEXT = "Error (this channel is not a text channel)"
CHOOSE_TEXT = "Please choose a text channel."
NO_HISTORY = "The bot cannot read this ticket's message history."
NO_TARGET = (
    "The bot lacks permissions in the target channel (VIEW_CHANNEL / MESSAGE_SEND / "
    "MESSAGE_SEND_IN_THREADS / CREATE_PUBLIC_THREADS / MANAGE_WEBHOOKS)"
)
WEBHOOKS = discord.Permissions(manage_webhooks=True).value
HISTORY = discord.Permissions(read_message_history=True).value


async def stored(scene: Scene) -> FakeChannel:
    """Panel 500's button 0, whose staff role is role 3, and text channel 6 to save into."""
    scene.guild.roles.append(FakeRole(3))
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [3], "categoryId": 0}]}
    )
    target = FakeChannel(id=TARGET, name="archive")
    scene.guild.channels.append(target)
    return target


def select_id(**fields: str) -> str:
    """The ID of the save select for member 8 and the panel's button 0, but for ``fields``."""
    return IDS.build({"action": "save", "sub_action": "select-channel", **FIELDS, **fields})


def told(interaction: FakeInteraction, text: str) -> bool:
    """Whether the interaction was answered with ``text`` alone, ephemerally."""
    return interaction.sent == [("response.send_message", {"content": text, "ephemeral": True})]


@pytest.mark.parametrize(
    ("locale", "text"),
    [("en-US", CHOOSE), ("zh-TW", GOLDEN["texts"]["zh-TW"]["choose-channel"])],
    ids=["en-US", "zh-TW"],
)
async def test_the_select(scene: Scene, locale: str, text: str) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    staff = scene.who(user=9, admin=False, roles=(3,), message_id=ROW, locale=locale)

    interaction = await scene.click("save", staff, **FIELDS)

    [(method, fields)] = interaction.sent
    assert method == "response.send_message"
    assert fields["content"] == text
    assert fields["ephemeral"] is True
    view = fields["view"]
    assert isinstance(view, discord.ui.View)
    assert view.is_finished()  # the router handles it, not discord.py
    [select] = view.children
    assert isinstance(select, discord.ui.ChannelSelect)
    assert select.custom_id == select_id()
    assert select.channel_types == [discord.ChannelType.text]
    assert (select.min_values, select.max_values) == (1, 1)
    assert select.placeholder == text


@pytest.mark.parametrize(
    ("locale", "text"),
    [("en-US", ADMIN_ONLY), ("zh-TW", GOLDEN["texts"]["zh-TW"]["admin-only"])],
    ids=["en-US", "zh-TW"],
)
async def test_not_a_staff_member(scene: Scene, locale: str, text: str) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    member = scene.who(user=8, admin=False, message_id=ROW, locale=locale)

    assert told(await scene.click("save", member, **FIELDS), text)


async def test_no_entry(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)

    interaction = await scene.click("save", scene.who(message_id=ROW), **FIELDS | {"msg_id": "1"})

    assert told(interaction, GOLDEN["texts"]["en-US"]["not-found"])


async def test_not_a_member(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    interaction = scene.button("save", scene.who(message_id=ROW), **FIELDS)
    interaction.user = FakeUser(id=7)  # Discord sent a user, not a member

    await scene.handle(interaction)

    # v3's deferEdit.
    assert interaction.sent == [("response.defer", {"ephemeral": False, "thinking": False})]


async def test_malformed_member(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)

    interaction = await scene.click("save", scene.who(message_id=ROW), **FIELDS | {"user_id": "x"})

    assert interaction.sent == []  # v3's cast threw before any answer


async def test_other_select(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    custom_id = select_id(sub_action="other")

    interaction = await scene.handle(scene.selection(custom_id, [str(TARGET)]))

    # v3's deferEdit.
    assert interaction.sent == [("response.defer", {"ephemeral": False, "thinking": False})]


@pytest.mark.parametrize(
    ("who", "fields", "text"),
    [
        ({"user": 8, "admin": False}, {}, ADMIN_ONLY),
        ({}, {"btn_index": "1"}, GOLDEN["texts"]["en-US"]["not-found"]),
    ],
    ids=["not-staff", "no-entry"],
)
async def test_refused_selections(
    scene: Scene, who: dict[str, int | bool], fields: dict[str, str], text: str
) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    target = await stored(scene)
    selection = scene.selection(select_id(**fields), [str(TARGET)], scene.who(**who))

    interaction = await scene.handle(selection)

    assert told(interaction, text)
    assert target.sent == []  # nothing archived


@pytest.mark.parametrize("control", ["button", "select"])
async def test_everyone_among_the_staff_roles(scene: Scene, control: str) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    target = await stored(scene)
    scene.guild.roles.append(scene.guild.default_role)
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [GUILD], "categoryId": 0}]}
    )
    # discord.py lists @everyone among every member's roles; JDA's getRoles left it out.
    member = scene.who(user=8, admin=False, roles=(GUILD,), message_id=ROW)

    if control == "button":
        interaction = await scene.click("save", member, **FIELDS)
    else:
        interaction = await scene.handle(scene.selection(select_id(), [str(TARGET)], member))

    assert told(interaction, ADMIN_ONLY)
    assert target.sent == []  # nothing archived


async def test_no_member(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    selection = scene.selection(select_id(), [str(TARGET)])
    selection.user = FakeUser(id=7)  # Discord sent a user, not a member

    assert told(await scene.handle(selection), NO_MEMBER)


async def test_not_a_text_channel(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    scene.channel = FakeChannel(id=5, type=discord.ChannelType.public_thread)

    assert told(await scene.handle(scene.selection(select_id(), [str(TARGET)])), NOT_TEXT)


@pytest.mark.parametrize(
    "values", [["7"], ["99"], ["abc"], []], ids=["voice", "unknown", "no-id", "none"]
)
async def test_no_text_channel_chosen(scene: Scene, values: list[str]) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    scene.guild.channels.append(FakeChannel(id=7, type=discord.ChannelType.voice))

    assert told(await scene.handle(scene.selection(select_id(), values)), CHOOSE_TEXT)


async def test_no_history_permission(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    await stored(scene)
    scene.channel.bot_permissions = discord.Permissions(discord.Permissions.all().value & ~HISTORY)

    assert told(await scene.handle(scene.selection(select_id(), [str(TARGET)])), NO_HISTORY)


async def test_no_target_permission(scene: Scene) -> None:
    """Requirement: Administrators choose where to save the conversation."""
    target = await stored(scene)
    target.bot_permissions = discord.Permissions(discord.Permissions.all().value & ~WEBHOOKS)

    interaction = await scene.handle(scene.selection(select_id(), [str(TARGET)]))

    assert told(interaction, NO_TARGET)
    assert target.sent == []  # nothing archived
