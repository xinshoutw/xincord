"""Component ID codec.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/ComponentIdManager.kt:13-247
"""

from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.component_ids import ComponentIdError, ComponentIds, ParsedId
from xincord.core.templates import load_message, render_message

if TYPE_CHECKING:
    from pathlib import Path

GIVEAWAY_FIELDS = ("action", "sub_action", "giveaway_id")
TICKET_FIELDS = ("action", "sub_action", "color_index", "user_id", "msg_id", "btn_index")


def giveaway() -> ComponentIds:
    return ComponentIds("giveaway", GIVEAWAY_FIELDS, legacy_prefix="giveaway@")


def ticket() -> ComponentIds:
    return ComponentIds("ticket", TICKET_FIELDS, legacy_prefix="ticket@", legacy_hex={"user_id"})


def test_build_and_parse() -> None:
    """Requirement: Component IDs use a versioned format."""
    ids = giveaway()

    custom_id = ids.build({"action": "join", "giveaway_id": 7})

    assert custom_id == "giveaway:1:a=join;c=7"
    assert ids.parse(custom_id) == ParsedId({"action": "join", "giveaway_id": "7"}, legacy=False)
    assert ids.parse("giveaway:1:") == ParsedId({}, legacy=False)


@pytest.mark.parametrize(
    "value", ["a;b=c:d%e", " two words ", chr(0x4E2D) + chr(0x6587), "", "~_.-"]
)
def test_values_are_escaped(value: str) -> None:
    """Requirement: Component IDs use a versioned format."""
    ids = giveaway()

    custom_id = ids.build({"sub_action": value, "action": "x"})

    assert custom_id.count(";") == 1
    assert custom_id.count("=") == 2
    assert custom_id.isascii()
    assert ids.parse(custom_id).fields == {"sub_action": value, "action": "x"}


def test_limits() -> None:
    """Requirement: Component IDs use a versioned format."""
    ids = giveaway()

    assert len(ids.build({"sub_action": "x" * 87})) == 100
    with pytest.raises(ComponentIdError, match="100"):
        ids.build({"sub_action": "x" * 88})
    with pytest.raises(ComponentIdError, match="color"):
        ids.build({"color": "red"})


@pytest.mark.parametrize(
    ("namespace", "fields", "hex_fields"),
    [
        ("Ticket", ("action",), ()),
        ("a:b", ("action",), ()),
        ("ticket", (), ()),
        ("ticket", tuple(f"f{index}" for index in range(27)), ()),
        ("ticket", ("action", "action"), ()),
        ("ticket", ("action",), ("user_id",)),
    ],
)
def test_invalid_codecs(
    namespace: str, fields: tuple[str, ...], hex_fields: tuple[str, ...]
) -> None:
    """Requirement: Component IDs use a versioned format."""
    with pytest.raises(ComponentIdError):
        ComponentIds(namespace, fields, legacy_hex=hex_fields)


def test_codec_as_template_id_builder(tmp_path: Path) -> None:
    """Requirement: Component IDs use a versioned format."""
    path = tmp_path / "template.yml"
    path.write_text(
        "components:\n  - !ButtonsComponent\n    buttons: [{uid: {action: join}, label: Join}]\n",
        encoding="utf-8",
    )

    message = render_message(load_message(path), {}, build_id=giveaway().build)

    assert message.view is not None
    (button,) = message.view.children
    assert isinstance(button, discord.ui.Button)
    assert button.custom_id == "giveaway:1:a=join"


def test_legacy_ticket_ids() -> None:
    """Requirement: Legacy v3 IDs decode permanently."""
    ids = ticket()

    assert ids.parse("ticket@a:submit;d:1b;f:2") == ParsedId(
        {"action": "submit", "user_id": "27", "btn_index": "2"}, legacy=True
    )
    assert ids.parse("ticket@a:create;b:modify-btn-color-submit;c:1").fields == {
        "action": "create",
        "sub_action": "modify-btn-color-submit",
        "color_index": "1",
    }
    assert ids.parse("ticket@a:").fields == {"action": ""}
    assert ids.parse("ticket@").fields == {}


@pytest.mark.parametrize(
    "custom_id",
    [
        "giveaway:1:a=join",
        "giveaway@a:join",
        "ticket@a",
        "ticket@z:x",
        "ticket@a:x:y",
        "ticket@a:x;",
        "ticket@d:xyz",
        "ticket@d:1_0",
        "ticket:1:z=x",
        "ticket:1:a",
        "ticket:1:a=%ff",
    ],
)
def test_foreign_and_malformed_ids(custom_id: str) -> None:
    """Requirement: Legacy v3 IDs decode permanently."""
    with pytest.raises(ComponentIdError):
        ticket().parse(custom_id)


def test_ownership() -> None:
    """Requirement: Legacy v3 IDs decode permanently."""
    ids = ticket()

    assert ids.owns("ticket:1:a=press")
    assert ids.owns("ticket@a:press")
    assert not ids.owns("giveaway:1:a=join")
    assert not ids.owns("ticket-addons:1:a=x")
    assert not ComponentIds("bot-info", ("action",)).owns("bot-info@a:x")
