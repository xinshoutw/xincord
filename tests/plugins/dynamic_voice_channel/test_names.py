"""The rooms' names, rendered from format 1."""

import pytest

from discord_fakes import BOT_USER, FakeGuild, FakeMember
from xincord.plugins.dynamic_voice_channel.names import custom_name, room_name, room_values

GUILD = FakeGuild(10)
EMOJI = chr(0x1F600)  # outside the BMP: two UTF-16 code units, as JDA counted them


@pytest.mark.parametrize(
    ("display_name", "expected"),
    [
        ("Bob - Gaming", "Bob"),
        ("Bob", "Bob"),
        ("A - B - C", "A"),
        ("Bob-Gaming", "Bob-Gaming"),
        ("Bob -Gaming", "Bob -Gaming"),
        (" - Gaming", ""),
        ("", ""),
    ],
)
def test_custom_name(display_name: str, expected: str) -> None:
    """Requirement: Room names follow format 1."""
    assert custom_name(display_name) == expected


def test_room_name_from_the_custom_name() -> None:
    """Requirement: Room names follow format 1."""
    bob = FakeMember(GUILD, id=7, name="bob", global_name="Bob - Gaming")

    assert room_name("| %dvc@custom_name%", room_values(bob, BOT_USER)) == "| Bob"


def test_member_values() -> None:
    """Requirement: Room names follow format 1."""
    bob = FakeMember(GUILD, id=7, name="alice", nick="Bob")
    values = room_values(bob, BOT_USER)

    assert values == {
        "bot_id": "99",
        "bot_name": "xincord",
        "user_id": "7",
        "user_mention": "<@7>",
        "user_name": "alice",
        "user_avatar_url": "https://cdn.example/default.png",
        "member_display_name": "Bob",
        "member_avatar_url": "https://cdn.example/default.png",
        "member_fixed_name": "Bob (alice)",
        "dvc@custom_name": "Bob",
    }
    template = "%member_display_name% %user_name% %bot_name%"
    assert room_name(template, values) == "Bob alice xincord"


def test_typed_text_stays() -> None:
    """Requirement: Room names follow format 1."""
    member = FakeMember(GUILD, id=7, name="alice", nick="%user_id%")

    # v3 expanded the display name again, into the member's ID.
    assert room_name("%dvc@custom_name%", room_values(member, BOT_USER)) == "%user_id%"
    assert room_name("%unknown% %dvc@custom_name%", {}) == "%unknown% %dvc@custom_name%"


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("  Bob  ", "Bob"),
        ("x" * 100, "x" * 100),
        (EMOJI * 50, EMOJI * 50),
    ],
)
def test_usable_name(template: str, expected: str) -> None:
    """Requirement: Room names follow format 1."""
    assert room_name(template, {}) == expected


@pytest.mark.parametrize(
    "template", ["", "   ", "%blank%", "x" * 101, EMOJI * 51, f" {'x' * 101} "]
)
def test_unusable_name(template: str) -> None:
    """Requirement: Room names follow format 1."""
    assert room_name(template, {"blank": "  "}) is None
