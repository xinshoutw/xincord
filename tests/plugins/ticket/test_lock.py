"""The control row's lock and unlock: the ticket's member loses or regains View Channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:148-179
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:784-832
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeMember, button_rows, forbidden
from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction, Sent

GOLDEN = golden("ticket")
MEMBER = 8  # the ticket's member
ROW = 901  # the control row's message in the ticket channel
FIELDS = {"user_id": str(MEMBER), "msg_id": "500", "btn_index": "0"}
DEFERRED: Sent = ("response.defer", {"ephemeral": False, "thinking": False})
VIEW = discord.Permissions(view_channel=True).value
SEND = discord.Permissions(send_messages=True).value


def controls(action: str) -> str:
    """The ID of the control row's button ``action`` for member 8 and the panel's button 0."""
    return IDS.build({"action": action, **FIELDS})


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
    assert deferred == DEFERRED  # at once: v3 answered after fetching the member and the overwrite
    assert method == "edit_original_response"
    assert list(fields) == ["view"]  # the components only
    view = fields["view"]
    assert isinstance(view, discord.ui.View)
    assert view.is_finished()  # the router handles its buttons, not discord.py
    return view


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The control row locks and unlocks the ticket",
)
async def test_lock_and_unlock(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    member = bob(scene)
    scene.channel.overwrites = {
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    staff = scene.who(message_id=ROW)

    locked = await scene.click("lock", staff, **FIELDS)
    unlocked = await scene.click("unlock", staff, **FIELDS)

    # View Channel is denied, then allowed; the overwrite's other permissions stay.
    assert overwrites(scene) == [(MEMBER, SEND, VIEW), (MEMBER, VIEW | SEND, 0)]
    zh = GOLDEN["texts"]["zh-TW"]
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


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The control row locks and unlocks the ticket",
)
async def test_cached_member(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    # discord.py has member 8; Discord would not answer a fetch (it has no members here).
    scene.guild.cached_members.append(FakeMember(scene.guild, id=MEMBER))

    interaction = await scene.click("lock", scene.who(message_id=ROW), **FIELDS)

    shown_row(interaction)
    assert overwrites(scene) == [(MEMBER, 0, VIEW)]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The control row locks and unlocks the ticket",
)
async def test_anyone_in_the_channel(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    bob(scene)
    member = scene.who(user=MEMBER, admin=False, message_id=ROW)

    # No permission check, as in v3: the member can lock themselves out.
    interaction = await scene.click("lock", member, **FIELDS)

    shown_row(interaction)
    assert overwrites(scene) == [(MEMBER, 0, VIEW)]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The control row locks and unlocks the ticket",
)
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
    with caplog.at_level(logging.WARNING):
        interaction = await scene.click("lock", scene.who(message_id=ROW, locale=locale), **FIELDS)

    reply = failed.replace("%tt@error%", "404 Not Found (error code: 0): Unknown Member")
    # The row stays as it was (v3: the press failed).
    assert interaction.sent == [DEFERRED, ("followup.send", {"content": reply, "ephemeral": True})]
    assert scene.channel.sent == []
    assert "Ticket cannot lock channel 5 for member 8" in caplog.text


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The control row locks and unlocks the ticket",
)
async def test_refused_overwrite(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
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


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The control row locks and unlocks the ticket",
)
async def test_channel_without_overwrites(scene: Scene) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    bob(scene)
    interaction = scene.button("lock", scene.who(message_id=ROW), **FIELDS)
    interaction.channel = None  # discord.py knew no such channel type

    await scene.handle(interaction)

    reply = "Changing the ticket's permissions failed: this channel has no permission overwrites"
    assert interaction.sent == [DEFERRED, ("followup.send", {"content": reply, "ephemeral": True})]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The control row locks and unlocks the ticket",
)
@pytest.mark.parametrize("fields", [{"user_id": "x"}, {}], ids=["not-a-number", "missing"])
async def test_malformed_member(scene: Scene, fields: dict[str, str]) -> None:
    """Requirement: The control row locks and unlocks the ticket."""
    bob(scene)

    interaction = await scene.click("lock", scene.who(message_id=ROW), msg_id="500", **fields)

    # v3's parse or cast threw before any answer.
    assert interaction.sent == []
    assert scene.channel.sent == []
