"""Deleting a ticket from the control row: its staff and administrators only; anyone else is told
so.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:181-196
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:834-852
"""

import logging
from typing import TYPE_CHECKING

import pytest

from discord_fakes import FakeRole, FakeUser, forbidden
from plugin_fakes import golden
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import Sent

GOLDEN = golden("ticket")
GUILD = 10  # the guild, whose ID its @everyone role shares
PANEL = "500"
ROW = 901  # the control row's message in the ticket channel
FIELDS = {"user_id": "8", "msg_id": PANEL, "btn_index": "0"}
DEFERRED: Sent = ("response.defer", {"ephemeral": False, "thinking": False})
DELETED: Sent = ("channel.delete", {"id": 5})
FAILED = "Deleting the ticket failed: "
ADMIN_ONLY = "Only administrators can use this."


async def stored(scene: Scene) -> None:
    """Panel 500's button 0, whose staff role is role 3."""
    scene.guild.roles.append(FakeRole(3))
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [3], "categoryId": 0}]}
    )


@pytest.mark.parametrize(
    ("roles", "admin"), [((3,), False), ((), True)], ids=["staff-role", "administrator"]
)
async def test_deletion(scene: Scene, roles: tuple[int, ...], admin: bool) -> None:  # noqa: FBT001
    """Requirement: Administrators delete the ticket."""
    await stored(scene)
    staff = scene.who(user=9, admin=admin, roles=roles, message_id=ROW)

    interaction = await scene.click("delete", staff, **FIELDS)

    assert interaction.sent == [DEFERRED]
    assert scene.channel.sent == [DELETED]


@pytest.mark.parametrize(
    ("user", "locale", "text"),
    [
        (8, "en-US", ADMIN_ONLY),
        (8, "zh-TW", GOLDEN["texts"]["zh-TW"]["admin-only"]),
        (9, "en-US", ADMIN_ONLY),
    ],
    ids=["the-tickets-member", "the-tickets-member-zh-TW", "another-member"],
)
async def test_not_a_staff_member(scene: Scene, user: int, locale: str, text: str) -> None:
    """Requirement: Administrators delete the ticket."""
    await stored(scene)
    member = scene.who(user=user, admin=False, message_id=ROW, locale=locale)

    interaction = await scene.click("delete", member, **FIELDS)

    # v3 acknowledged the press and did nothing.
    assert interaction.sent == [("response.send_message", {"content": text, "ephemeral": True})]
    assert scene.channel.sent == []  # the channel stays


async def test_everyone_among_the_staff_roles(scene: Scene) -> None:
    """Requirement: Administrators delete the ticket."""
    scene.guild.roles.append(scene.guild.default_role)
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [GUILD], "categoryId": 0}]}
    )
    # discord.py lists @everyone among every member's roles; JDA's getRoles left it out.
    member = scene.who(user=8, admin=False, roles=(GUILD,), message_id=ROW)

    interaction = await scene.click("delete", member, **FIELDS)

    assert interaction.sent == [
        ("response.send_message", {"content": ADMIN_ONLY, "ephemeral": True})
    ]
    assert scene.channel.sent == []  # the channel stays


async def test_not_a_member(scene: Scene) -> None:
    """Requirement: Administrators delete the ticket."""
    await stored(scene)
    interaction = scene.button("delete", scene.who(message_id=ROW), **FIELDS)
    interaction.user = FakeUser(id=7)  # Discord sent a user, not a member

    await scene.handle(interaction)

    assert interaction.sent == [DEFERRED]
    assert scene.channel.sent == []


@pytest.mark.parametrize(
    "fields",
    [{"msg_id": "501", "btn_index": "0"}, {"msg_id": PANEL, "btn_index": "1"}, {}],
    ids=["other-message", "other-index", "missing"],
)
async def test_no_entry(scene: Scene, fields: dict[str, str]) -> None:
    """Requirement: Administrators delete the ticket."""
    await stored(scene)

    interaction = await scene.click("delete", scene.who(message_id=ROW), user_id="8", **fields)

    reply = GOLDEN["texts"]["en-US"]["not-found"]
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]
    assert scene.channel.sent == []


async def test_refused_deletion(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Administrators delete the ticket."""
    await stored(scene)
    scene.channel.delete_error = forbidden()

    with caplog.at_level(logging.WARNING):
        interaction = await scene.click("delete", scene.who(message_id=ROW), **FIELDS)

    reply = FAILED + "403 Forbidden (error code: 0): Missing Permissions"
    assert interaction.sent == [DEFERRED, ("followup.send", {"content": reply, "ephemeral": True})]
    assert "Ticket cannot delete the ticket channel 5" in caplog.text


async def test_channel_that_cannot_be_deleted(scene: Scene) -> None:
    """Requirement: Administrators delete the ticket."""
    await stored(scene)
    interaction = scene.button("delete", scene.who(message_id=ROW), **FIELDS)
    interaction.channel = None  # discord.py knew no such channel type

    await scene.handle(interaction)

    reply = FAILED + "this channel cannot be deleted"
    assert interaction.sent == [DEFERRED, ("followup.send", {"content": reply, "ephemeral": True})]
