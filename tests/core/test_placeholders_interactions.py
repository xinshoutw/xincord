"""Interaction placeholder values.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:59-142
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import discord

from xincord.core.placeholders import interaction_values, locale_names

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload
    from discord.types.components import ContainerComponent as ContainerPayload


@dataclass
class FakeMessage:
    components: list[object]


@dataclass
class FakeInteraction:
    data: dict[str, object] | None
    locale: discord.Locale = discord.Locale.american_english
    channel: object = None
    message: FakeMessage | None = None


def slash(*options: dict[str, object]) -> dict[str, object]:
    create = {"type": 1, "name": "create", "options": list(options)}
    return {
        "type": 1,
        "name": "ticket",
        "options": [{"type": 2, "name": "panel", "options": [create]}],
        "resolved": {
            "channels": {"10": {"id": "10", "name": "general"}},
            "users": {"20": {"id": "20", "username": "alice"}},
            "roles": {"30": {"id": "30", "name": "Mods"}},
        },
    }


def test_subcommand_with_options() -> None:
    """Requirement: Command interaction values follow v3."""
    data = slash(
        {"type": 7, "name": "where", "value": "10"},
        {"type": 6, "name": "owner", "value": "20"},
        {"type": 8, "name": "role", "value": "30"},
        {"type": 5, "name": "pinned", "value": True},
        {"type": 3, "name": "title", "value": "Hi"},
    )

    values = interaction_values(FakeInteraction(data))

    assert values["command_string"] == (
        "/ticket panel create where: #general owner: @alice role: @Mods pinned: true title: Hi"
    )
    assert values["command_name"] == "ticket"
    assert values["full_command_name"] == "ticket panel create"
    assert values["subcommand_name"] == "create"


def test_mentionables_numbers_and_unresolved_entities() -> None:
    """Requirement: Command interaction values follow v3."""
    data = slash(
        {"type": 9, "name": "who", "value": "20"},
        {"type": 9, "name": "group", "value": "30"},
        {"type": 6, "name": "ghost", "value": "99"},
        {"type": 4, "name": "count", "value": 3},
    )

    values = interaction_values(FakeInteraction(data))

    assert values["command_string"] == (
        "/ticket panel create who: @alice group: @Mods ghost: 99 count: 3"
    )


def test_context_menu_command() -> None:
    """Requirement: Command interaction values follow v3."""
    values = interaction_values(FakeInteraction({"type": 3, "name": "Report", "target_id": "1"}))

    assert values["command_name"] == "Report"
    assert values["full_command_name"] == "Report"
    assert values["command_string"] == "Report"
    assert "subcommand_name" not in values


def components() -> FakeMessage:
    button = {
        "type": 2,
        "style": 1,
        "custom_id": "ticket:1:a=press",
        "label": "Open",
        "emoji": {"name": "join", "id": "112233445566778899"},
    }
    select = {
        "type": 3,
        "custom_id": "pick",
        "options": [{"label": "a", "value": "a"}],
        "placeholder": "Choose",
        "min_values": 1,
        "max_values": 2,
    }
    plain = {"type": 2, "style": 4, "custom_id": "stop", "label": "Stop"}
    bare = {"type": 3, "custom_id": "bare", "options": [{"label": "a", "value": "a"}]}
    container = {"type": 17, "components": [{"type": 1, "components": [button, plain]}]}
    return FakeMessage(
        [
            discord.Container(cast("ContainerPayload", container), None),
            discord.ActionRow(cast("ActionRowPayload", {"type": 1, "components": [select]})),
            discord.ActionRow(cast("ActionRowPayload", {"type": 1, "components": [bare]})),
        ]
    )


def component_keys(custom_id: str, message: FakeMessage | None) -> dict[str, str]:
    data: dict[str, object] = {"custom_id": custom_id, "component_type": 2}
    values = interaction_values(FakeInteraction(data, message=message))
    return {key: value for key, value in values.items() if key.startswith("component_")}


def test_button_and_select() -> None:
    """Requirement: Component interaction values follow v3."""
    assert component_keys("ticket:1:a=press", components()) == {
        "component_id": "ticket:1:a=press",
        "component_label": "Open",
        "component_style": "PRIMARY",
        "component_emoji": "<:join:112233445566778899>",
        "component_emoji_name": "join",
    }
    assert component_keys("pick", components()) == {
        "component_id": "pick",
        "component_min": "1",
        "component_max": "2",
        "component_placeholder": "Choose",
    }
    assert component_keys("stop", components()) == {
        "component_id": "stop",
        "component_label": "Stop",
        "component_style": "DANGER",
    }
    assert component_keys("bare", components()) == {
        "component_id": "bare",
        "component_min": "1",
        "component_max": "1",
    }


def test_unknown_component() -> None:
    """Requirement: Component interaction values follow v3."""
    assert component_keys("gone", components()) == {"component_id": "gone"}
    assert component_keys("gone", None) == {"component_id": "gone"}


def test_guild_channel_and_direct_message() -> None:
    """Requirement: Interaction language and channel follow v3."""
    channel = SimpleNamespace(id=5, name="general", category=SimpleNamespace(name="Text"))
    lobby = SimpleNamespace(id=6, name="lobby", category=None)
    data: dict[str, object] = {"custom_id": "x", "component_type": 2}

    guild = interaction_values(FakeInteraction(data, discord.Locale.taiwan_chinese, channel))
    uncategorized = interaction_values(FakeInteraction(data, channel=lobby))
    direct = interaction_values(FakeInteraction(None, channel=SimpleNamespace(id=7)))

    assert guild["language"] == locale_names("zh-TW")[1]
    assert (guild["channel_id"], guild["channel_name"]) == ("5", "general")
    assert guild["channel_category_name"] == "Text"
    assert "channel_category_name" not in uncategorized
    assert direct == {"language": locale_names("en-US")[1]}


class OrphanThread:
    """A thread whose parent channel discord.py has not cached, as in a guild it never cached."""

    id = 8
    name = "help"

    @property
    def category(self) -> object:
        """discord.py's ``Thread.category`` raises when the parent is unknown."""
        msg = "Parent channel not found"
        raise discord.ClientException(msg)


def test_thread_with_an_uncached_parent() -> None:
    """Requirement: Interaction language and channel follow v3."""
    values = interaction_values(FakeInteraction({"type": 1, "name": "x"}, channel=OrphanThread()))

    assert (values["channel_id"], values["channel_name"]) == ("8", "help")
    assert "channel_category_name" not in values


def discord_interaction_fits(interaction: discord.Interaction) -> None:
    """Type check only: discord.py's interactions satisfy the Protocol."""
    interaction_values(interaction)
