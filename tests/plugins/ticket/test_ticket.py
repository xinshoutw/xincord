"""Submitting the reason opens a ticket channel with v3's overwrites, the bot's, and its opener.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:248-310
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:784-832
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import BOT_USER, FakeCategory, FakeChannel, FakeRole, button_rows, forbidden
from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.store import NAMESPACE
from xincord.plugins.ticket.texts import chunks

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction, Sent
    from xincord.core.storage import JSON

GOLDEN = golden("ticket")
PANEL = "500"
MEMBER = 8
CATEGORY = 30
GO = "Please go to <#700> and wait for a staff member to reply."


@dataclass
class Ticket:
    """The scene of a ticket: the panel channel's category, and the submission."""

    category: FakeCategory
    interaction: FakeInteraction


def controls(action: str) -> str:
    """The ID of the control row's button ``action`` for member 8 and the panel's button 0."""
    return IDS.build({"action": action, "user_id": str(MEMBER), "msg_id": PANEL, "btn_index": "0"})


async def open_ticket(
    scene: Scene, reason: str = "help me", category_id: int = 0, admins: list[int] | None = None
) -> Ticket:
    """Member 8 (bob) submits ``reason`` from the panel's button 0, whose entry is stored."""
    scene.guild.roles.extend([FakeRole(3), FakeRole(4)])
    category = FakeCategory(id=CATEGORY)
    scene.guild.channels.append(category)
    scene.channel.category = category
    admin_ids: list[JSON] = [*(admins or [3, 4])]
    entry: JSON = {"reasonTitle": "Why?", "adminIds": admin_ids, "categoryId": category_id}
    await scene.store.put(NAMESPACE, "10", {PANEL: [entry]})
    custom_id = IDS.build({"action": "submit", "msg_id": PANEL, "btn_index": "0"})
    who = scene.who(user=MEMBER, name="bob", admin=False, message_id=int(PANEL))
    interaction = await scene.submit_id(custom_id, {"reason": reason}, who)
    return Ticket(category, interaction)


def sends(sent: list[Sent]) -> list[dict[str, object]]:
    """The messages sent to the ticket channel."""
    return [fields for method, fields in sent if method == "channel.send"]


def pairs(overwrites: object) -> dict[int, tuple[int, int]]:
    """Each overwrite's target ID with its allowed and denied permissions."""
    found: dict[int, tuple[int, int]] = {}
    for target, overwrite in cast("dict[object, discord.PermissionOverwrite]", overwrites).items():
        allow, deny = overwrite.pair()
        found[cast("int", getattr(target, "id", None))] = (allow.value, deny.value)
    return found


VIEW = discord.Permissions(view_channel=True).value
SEND = discord.Permissions(send_messages=True).value


async def test_ticket(scene: Scene) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    ticket = await open_ticket(scene)

    assert ticket.interaction.sent == [
        ("response.defer", {"ephemeral": True, "thinking": True}),
        ("edit_original_response", {"content": GO}),
    ]
    (created, opener) = ticket.category.sent
    assert created[0] == "category.create_text_channel"
    assert created[1]["name"] == "bob"  # the member's username, as in v3
    assert opener[0] == "channel.send"
    fields = opener[1]
    assert fields["content"] == "<@&3> <@&4> \n\nhelp me"
    zh = GOLDEN["texts"]["zh-TW"]
    assert button_rows(fields["view"]) == [
        [
            (zh["lock"], controls("lock"), 2),
            (zh["save"], controls("save"), 1),
            (zh["delete"], controls("delete"), 4),
        ]
    ]
    view = fields["view"]
    assert isinstance(view, discord.ui.View)
    assert view.is_finished()
    emojis = [str(getattr(item, "emoji", None)) for item in view.children]
    assert emojis == [chr(0x1F512), chr(0x1F4BE), chr(0x1F5D1)]
    mentions = fields["allowed_mentions"]
    assert isinstance(mentions, discord.AllowedMentions)
    # The staff roles ping, nothing typed does (v3 pinged everything, S1).
    assert mentions.everyone is False
    assert [role.id for role in cast("list[discord.Object]", mentions.roles)] == [3, 4]


async def test_public_texts_in_the_default_locale(scene: Scene) -> None:
    """Requirement: Texts follow the reader."""
    ticket = await open_ticket(scene)  # member 8's client is en-US

    [fields] = sends(ticket.category.sent)
    labels = [label for label, _, _ in button_rows(fields["view"])[0]]
    zh = GOLDEN["texts"]["zh-TW"]
    assert labels == [zh["lock"], zh["save"], zh["delete"]]


async def test_configured_category(scene: Scene) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    other = FakeCategory(id=31)
    scene.guild.channels.append(other)

    ticket = await open_ticket(scene, category_id=31)

    assert [method for method, _ in other.sent] == ["category.create_text_channel", "channel.send"]
    assert ticket.category.sent == []


async def test_panel_in_a_thread(scene: Scene) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    category = FakeCategory(id=CATEGORY)
    scene.channel = FakeChannel(
        id=6, type=discord.ChannelType.public_thread, parent=FakeChannel(id=5, category=category)
    )
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [], "categoryId": 0}]}
    )
    custom_id = IDS.build({"action": "submit", "msg_id": PANEL, "btn_index": "0"})

    await scene.submit_id(custom_id, {"reason": "x"}, scene.who(user=MEMBER, admin=False))

    # v3's asTextChannel() threw in a thread; the thread's channel's category serves.
    assert [method for method, _ in category.sent] == [
        "category.create_text_channel",
        "channel.send",
    ]


@pytest.mark.parametrize(
    ("missing", "reply"),
    [
        ("entry", GOLDEN["texts"]["en-US"]["not-found"]),
        ("category", "Error (the category cannot be found)"),
        ("panel category", "Error (the category cannot be found)"),
    ],
)
async def test_missing_entry_or_category(scene: Scene, missing: str, reply: str) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    scene.channel.category = None if missing == "panel category" else FakeCategory(id=CATEGORY)
    entry: JSON = {
        "reasonTitle": "Why?",
        "adminIds": [],
        "categoryId": 31 if missing == "category" else 0,
    }
    if missing != "entry":
        await scene.store.put(NAMESPACE, "10", {PANEL: [entry]})
    custom_id = IDS.build({"action": "submit", "msg_id": PANEL, "btn_index": "0"})

    interaction = await scene.submit_id(custom_id, {"reason": "x"}, scene.who(user=MEMBER))

    # v3 threw (B4), or replied after deferring, which never arrived (B3).
    assert interaction.sent == [
        ("response.defer", {"ephemeral": True, "thinking": True}),
        ("edit_original_response", {"content": reply}),
    ]


async def test_long_reason(scene: Scene) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    ticket = await open_ticket(scene, reason="x" * 2100)

    parts = sends(ticket.category.sent)
    # v3 threw above 2000 characters and left the channel without controls (B10).
    assert [len(cast("str", fields["content"])) for fields in parts] == [2000, 114]
    assert "".join(cast("str", fields["content"]) for fields in parts) == (
        "<@&3> <@&4> \n\n" + "x" * 2100
    )
    assert [fields.get("view") is not None for fields in parts] == [False, True]


@pytest.mark.parametrize("refused", ["channel", "opener"])
async def test_refused_creation(scene: Scene, refused: str) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    category = FakeCategory(id=CATEGORY)
    if refused == "channel":
        category.create_error = forbidden()
    else:
        category.send_error = forbidden()
    scene.channel.category = category
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [], "categoryId": 0}]}
    )
    custom_id = IDS.build({"action": "submit", "msg_id": PANEL, "btn_index": "0"})

    interaction = await scene.submit_id(custom_id, {"reason": "x"}, scene.who(user=MEMBER))

    reply = "Opening the ticket failed: 403 Forbidden (error code: 0): Missing Permissions"
    assert interaction.sent[-1] == ("edit_original_response", {"content": reply})
    methods = [method for method, _ in category.sent]
    # A channel without its control row is deleted (v3 left it, B10).
    assert methods == (
        [] if refused == "channel" else ["category.create_text_channel", "channel.delete"]
    )


async def test_overwrites(scene: Scene) -> None:
    """Requirement: Ticket channels get v3's permissions and the bot's."""
    role5, everyone = FakeRole(5), scene.guild.default_role
    category = FakeCategory(id=CATEGORY)
    category.overwrites = {
        role5: discord.PermissionOverwrite(send_messages=True),
        everyone: discord.PermissionOverwrite(send_messages=False),
    }
    scene.channel.category = category
    scene.guild.roles.extend([FakeRole(3), FakeRole(4)])
    entry: JSON = {"reasonTitle": "Why?", "adminIds": [3, 4, 6], "categoryId": 0}  # 6 is gone
    await scene.store.put(NAMESPACE, "10", {PANEL: [entry]})
    custom_id = IDS.build({"action": "submit", "msg_id": PANEL, "btn_index": "0"})

    await scene.submit_id(custom_id, {"reason": "x"}, scene.who(user=MEMBER))

    created = category.sent[0][1]["overwrites"]
    assert pairs(created) == {
        5: (SEND, 0),  # the category's, copied as JDA's createTextChannel did
        10: (0, VIEW),  # @everyone denied View Channel only (its copied deny goes, as in v3)
        MEMBER: (VIEW, 0),
        3: (VIEW, 0),
        4: (VIEW, 0),
        BOT_USER.id: (VIEW, 0),  # the bot's own (v3 had none, B11)
    }


@pytest.mark.parametrize("administrator", [False, True])
async def test_overwrites_the_bot_cannot_copy(scene: Scene, administrator: bool) -> None:  # noqa: FBT001
    """Requirement: Ticket channels get v3's permissions and the bot's."""
    category = FakeCategory(id=CATEGORY, bot_permissions=discord.Permissions(view_channel=True))
    category.overwrites = {
        FakeRole(5): discord.PermissionOverwrite(manage_messages=True),  # the bot lacks it
        discord.Object(9, type=discord.Role): discord.PermissionOverwrite(view_channel=True),
    }
    scene.guild.permissions = discord.Permissions(administrator=administrator)
    scene.channel.category = category
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [], "categoryId": 0}]}
    )
    custom_id = IDS.build({"action": "submit", "msg_id": PANEL, "btn_index": "0"})

    await scene.submit_id(custom_id, {"reason": "x"}, scene.who(user=MEMBER))

    created = pairs(category.sent[0][1]["overwrites"])
    # JDA's trySync copied nothing then, unless the bot could sync; an uncached role never goes.
    expected = {10: (0, VIEW), MEMBER: (VIEW, 0), BOT_USER.id: (VIEW, 0)}
    if administrator:
        expected[5] = (discord.Permissions(manage_messages=True).value, 0)
    assert created == expected


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("abc", ["abc"]),
        ("x" * 4000, ["x" * 2000, "x" * 2000]),
        # A character outside the BMP counts twice and is never split.
        ("x" * 1999 + chr(0x1F3AB) + "y", ["x" * 1999, chr(0x1F3AB) + "y"]),
        ("", [""]),
    ],
)
def test_chunks(text: str, parts: list[str]) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    assert chunks(text, 2000) == parts


async def test_undeletable_channel(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Submitting the reason opens a ticket channel."""
    category = FakeCategory(id=CATEGORY, send_error=forbidden(), channel_delete_error=forbidden())
    scene.channel.category = category
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [], "categoryId": 0}]}
    )
    custom_id = IDS.build({"action": "submit", "msg_id": PANEL, "btn_index": "0"})

    interaction = await scene.submit_id(custom_id, {"reason": "x"}, scene.who(user=MEMBER))

    assert interaction.sent[-1][0] == "edit_original_response"
    assert "cannot delete the channel 700" in caplog.text
