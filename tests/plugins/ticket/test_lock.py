"""The control row's lock and unlock: the ticket's member loses or regains View Channel, for the
ticket's staff only.
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeMember, FakeRole, FakeUser, button_rows, forbidden
from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction, Sent
    from xincord.core.storage import JSON

GOLDEN = golden("ticket")
GUILD = 10  # the guild, whose ID its @everyone role shares
MEMBER = 8  # the ticket's member
PANEL = "500"
ROW = 901  # the control row's message in the ticket channel
FIELDS = {"user_id": str(MEMBER), "msg_id": PANEL, "btn_index": "0"}
DEFERRED: Sent = ("response.defer", {"ephemeral": False, "thinking": False})
VIEW = discord.Permissions(view_channel=True).value
SEND = discord.Permissions(send_messages=True).value
ADMIN_ONLY = "Only administrators can use this."


async def stored(scene: Scene) -> None:
    """Panel 500's button 0, whose staff role is role 3."""
    scene.guild.roles.append(FakeRole(3))
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [3], "categoryId": 0}]}
    )


def controls(action: str) -> str:
    """The ID of the control row's button ``action`` for member 8 and the panel's button 0."""
    return IDS.build({"action": action, **FIELDS})


async def everyone_on_staff(scene: Scene) -> None:
    """Panel 500's button 0, whose staff roles are @everyone and role 3."""
    scene.guild.roles.extend([scene.guild.default_role, FakeRole(3)])
    entry: JSON = {"reasonTitle": "Why?", "adminIds": [GUILD, 3], "categoryId": 0}
    await scene.store.put(NAMESPACE, "10", {PANEL: [entry]})


def bob(scene: Scene) -> FakeMember:
    """Member 8 of guild 10, as Discord has them; discord.py has not cached them."""
    member = FakeMember(scene.guild, id=MEMBER, name="bob")
    scene.guild.members.append(member)
    return member


def overwrites(scene: Scene) -> list[tuple[object, int, int]]:
    """Each overwrite that the plugin set: its member, and what it allows and denies."""
    found: list[tuple[object, int, int]] = []
    for method, fields in scene.channel.sent:
        if method == "channel.set_permissions":
            allow, deny = cast("discord.PermissionOverwrite", fields["overwrite"]).pair()
            found.append((fields["target"], allow.value, deny.value))
    return found


def shown_row(interaction: FakeInteraction) -> discord.ui.View:
    """The control row that the press showed instead of the pressed one."""
    [deferred, (method, fields)] = interaction.sent
    assert deferred == DEFERRED  # at once, before the member and the overwrite
    assert method == "edit_original_response"
    assert list(fields) == ["view"]  # the components only
    view = fields["view"]
    assert isinstance(view, discord.ui.View)
    assert view.is_finished()  # the router handles its buttons, not discord.py
    return view


async def test_lock_and_unlock(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    member = bob(scene)
    scene.channel.overwrites = {
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    staff = scene.who(message_id=ROW)

    locked = await scene.click("lock", staff, **FIELDS)
    unlocked = await scene.click("unlock", staff, **FIELDS)

    # View Channel is denied, then allowed; the overwrite's other permissions stay.
    assert overwrites(scene) == [(MEMBER, SEND, VIEW), (MEMBER, VIEW | SEND, 0)]
    zh = GOLDEN["labels"]["zh-TW"]  # the owner's labels, in the default locale
    row = shown_row(locked)
    assert button_rows(row) == [
        [
            (zh["unlock"], controls("unlock"), 3),
            (zh["save"], controls("save"), 1),
            (zh["delete"], controls("delete"), 4),
        ]
    ]
    assert [str(getattr(item, "emoji", None)) for item in row.children] == [
        chr(0x1F513),
        chr(0x1F4BE),
        chr(0x1F5D1),
    ]
    assert button_rows(shown_row(unlocked)) == [
        [
            (zh["lock"], controls("lock"), 2),
            (zh["save"], controls("save"), 1),
            (zh["delete"], controls("delete"), 4),
        ]
    ]


async def test_cached_member(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    # discord.py has member 8; Discord would not answer a fetch (it has no members here).
    scene.guild.cached_members.append(FakeMember(scene.guild, id=MEMBER))

    interaction = await scene.click("lock", scene.who(message_id=ROW), **FIELDS)

    shown_row(interaction)
    assert overwrites(scene) == [(MEMBER, 0, VIEW)]


async def test_staff_role(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    bob(scene)
    staff = scene.who(user=9, admin=False, roles=(3,), message_id=ROW)

    interaction = await scene.click("lock", staff, **FIELDS)

    shown_row(interaction)
    assert overwrites(scene) == [(MEMBER, 0, VIEW)]


@pytest.mark.parametrize("action", ["lock", "unlock"])
@pytest.mark.parametrize(
    ("user", "locale", "text"),
    [
        (MEMBER, "en-US", ADMIN_ONLY),
        (MEMBER, "zh-TW", GOLDEN["texts"]["zh-TW"]["admin-only"]),
        (9, "en-US", ADMIN_ONLY),
    ],
    ids=["the-tickets-member", "the-tickets-member-zh-TW", "another-member"],
)
async def test_not_the_tickets_staff(
    scene: Scene, action: str, user: int, locale: str, text: str
) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    bob(scene)
    member = scene.who(user=user, admin=False, message_id=ROW, locale=locale)

    interaction = await scene.click(action, member, **FIELDS)

    # The member cannot lock themselves out.
    assert interaction.sent == [("response.send_message", {"content": text, "ephemeral": True})]
    assert scene.channel.sent == []  # no overwrite changes


@pytest.mark.parametrize(
    "fields",
    [{"msg_id": "501", "btn_index": "0"}, {"msg_id": PANEL, "btn_index": "1"}, {}],
    ids=["other-message", "other-index", "missing"],
)
async def test_no_entry(scene: Scene, fields: dict[str, str]) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    bob(scene)
    staff = scene.who(message_id=ROW)

    interaction = await scene.click("unlock", staff, user_id=str(MEMBER), **fields)

    reply = GOLDEN["texts"]["en-US"]["not-found"]
    assert interaction.sent == [("response.send_message", {"content": reply, "ephemeral": True})]
    assert scene.channel.sent == []


async def test_not_a_member(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    bob(scene)
    interaction = scene.button("lock", scene.who(message_id=ROW), **FIELDS)
    interaction.user = FakeUser(id=7)  # Discord sent a user, not a member

    await scene.handle(interaction)

    # A deferred update, as save and delete answer it, and nothing else.
    assert interaction.sent == [DEFERRED]
    assert scene.channel.sent == []


@pytest.mark.parametrize("action", ["lock", "unlock"])
async def test_everyone_among_the_staff_roles(scene: Scene, action: str) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await everyone_on_staff(scene)
    bob(scene)
    # discord.py lists @everyone among every member's roles.
    member = scene.who(user=MEMBER, admin=False, roles=(GUILD,), message_id=ROW)

    interaction = await scene.click(action, member, **FIELDS)

    assert interaction.sent == [
        ("response.send_message", {"content": ADMIN_ONLY, "ephemeral": True})
    ]
    assert scene.channel.sent == []


async def test_staff_role_beside_everyone(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await everyone_on_staff(scene)
    bob(scene)
    staff = scene.who(user=9, admin=False, roles=(GUILD, 3), message_id=ROW)

    interaction = await scene.click("lock", staff, **FIELDS)

    shown_row(interaction)
    assert overwrites(scene) == [(MEMBER, 0, VIEW)]


@pytest.mark.parametrize(
    ("locale", "failed"),
    [
        ("en-US", "Changing the ticket's permissions failed: %tt@error%"),
        ("zh-TW", GOLDEN["texts"]["zh-TW"]["lock-failed"]),
    ],
    ids=["en-US", "zh-TW"],
)
async def test_member_who_left(
    scene: Scene, caplog: pytest.LogCaptureFixture, locale: str, failed: str
) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    with caplog.at_level(logging.WARNING):
        interaction = await scene.click("lock", scene.who(message_id=ROW, locale=locale), **FIELDS)

    reply = failed.replace("%tt@error%", "404 Not Found (error code: 0): Unknown Member")
    # The row stays as it was.
    assert interaction.sent == [DEFERRED, ("followup.send", {"content": reply, "ephemeral": True})]
    assert scene.channel.sent == []
    assert "Ticket cannot lock channel 5 for member 8" in caplog.text


async def test_refused_overwrite(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    bob(scene)
    scene.channel.permissions_error = forbidden()

    with caplog.at_level(logging.WARNING):
        interaction = await scene.click("unlock", scene.who(message_id=ROW), **FIELDS)

    reply = (
        "Changing the ticket's permissions failed: "
        "403 Forbidden (error code: 0): Missing Permissions"
    )
    assert interaction.sent == [DEFERRED, ("followup.send", {"content": reply, "ephemeral": True})]
    assert "Ticket cannot unlock channel 5 for member 8" in caplog.text


async def test_channel_without_overwrites(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    bob(scene)
    interaction = scene.button("lock", scene.who(message_id=ROW), **FIELDS)
    interaction.channel = None  # discord.py knew no such channel type

    await scene.handle(interaction)

    reply = "Changing the ticket's permissions failed: this channel has no permission overwrites"
    assert interaction.sent == [DEFERRED, ("followup.send", {"content": reply, "ephemeral": True})]


@pytest.mark.parametrize("fields", [{"user_id": "x"}, {}], ids=["not-a-number", "missing"])
async def test_malformed_member(scene: Scene, fields: dict[str, str]) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    await stored(scene)
    bob(scene)

    interaction = await scene.click("lock", scene.who(message_id=ROW), msg_id=PANEL, **fields)

    # No answer.
    assert interaction.sent == []
    assert scene.channel.sent == []
