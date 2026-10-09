"""Components V2 rendering.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/builder/MessageBuilder.kt:56-536
"""

from pathlib import Path
from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.templates import Message, TemplateError, load_message, render_message

if TYPE_CHECKING:
    from collections.abc import Mapping

EXAMPLE = Path(__file__).parent.parent / "fixtures" / "templates" / "components_v2_example.yml"
VALUES = {"user_name": "Alice", "file": "report"}
V2 = "is_components_v2: true\n"


def build_id(uid: Mapping[str, str]) -> str:
    return "id:" + ",".join(f"{key}={value}" for key, value in uid.items())


def render(tmp_path: Path, text: str, *, models: Mapping[str, object] | None = None) -> Message:
    path = tmp_path / "template.yml"
    path.write_text(text, encoding="utf-8")
    return render_message(load_message(path), VALUES, build_id=build_id, models=models)


def layout(message: Message) -> discord.ui.LayoutView:
    assert isinstance(message.view, discord.ui.LayoutView)
    assert message.view.is_finished()
    return message.view


async def test_section_gallery_and_container(tmp_path: Path) -> None:
    """Requirement: V2 messages render into a layout view."""
    text = V2 + (
        "components_v2:\n"
        "  - type: section\n"
        "    id: 1\n"
        "    components: [{type: text_display, id: 2, content: 'Hi %user_name%'}]\n"
        "    accessory: {type: thumbnail, url: 'https://e.com/%user_name%.png', description: Pic}\n"
        "  - type: media_gallery\n"
        "    id: 3\n"
        "    items:\n"
        "      - {url: 'https://e.com/b.png', description: 'B %user_name%', spoiler: true}\n"
        "      - {file_name: '%file%.png'}\n"
        "  - type: container\n"
        "    id: 4\n"
        "    accent_color: '#4A90E2'\n"
        "    components:\n"
        "      - {type: separator, divider: false, spacing: large}\n"
        "      - {type: text_display, content: 'In %user_name%'}\n"
    )

    message = render(tmp_path, text)

    assert (message.content, message.embeds, message.files) == ("", (), ())
    assert layout(message).to_components() == [
        {
            "type": 9,
            "id": 1,
            "components": [{"type": 10, "id": 2, "content": "Hi Alice"}],
            "accessory": {
                "type": 11,
                "media": {"url": "https://e.com/Alice.png"},
                "description": "Pic",
                "spoiler": False,
            },
        },
        {
            "type": 12,
            "id": 3,
            "items": [
                {
                    "media": {"url": "https://e.com/b.png"},
                    "description": "B Alice",
                    "spoiler": True,
                },
                {"media": {"url": "attachment://report.png"}, "spoiler": False},
            ],
        },
        {
            "type": 17,
            "id": 4,
            "accent_color": 0x4A90E2,
            "spoiler": False,
            "components": [
                {"type": 14, "divider": False, "spacing": 2},
                {"type": 10, "content": "In Alice"},
            ],
        },
    ]


async def test_full_example_renders() -> None:
    """Requirement: V2 messages render into a layout view."""
    message = render_message(load_message(EXAMPLE), VALUES, build_id=build_id)

    items = layout(message).children
    assert [type(item).__name__ for item in items] == [
        "Section",
        "Section",
        "ActionRow",
        "ActionRow",
        "ActionRow",
        "ActionRow",
        "MediaGallery",
        "Separator",
        "File",
        "Container",
    ]
    assert [item.id for item in items] == list(range(1001, 1011))


async def test_local_files(tmp_path: Path) -> None:
    """Requirement: V2 messages render into a layout view."""
    (tmp_path / "report.txt").write_text("data", encoding="utf-8")
    (tmp_path / "chart.png").write_bytes(b"png")
    text = V2 + (
        "components_v2:\n"
        f"  - {{type: file_display, file_path: '{tmp_path}/%file%.txt', spoiler: true}}\n"
        f"  - {{type: media_gallery, items: [{{file_path: '{tmp_path}/chart.png'}}]}}\n"
    )

    message = render(tmp_path, text)

    try:
        assert [file.filename for file in message.files] == ["report.txt", "chart.png"]
        assert layout(message).to_components() == [
            {"type": 13, "file": {"url": "attachment://report.txt"}, "spoiler": True},
            {"type": 12, "items": [{"media": {"url": "attachment://chart.png"}, "spoiler": False}]},
        ]
    finally:
        for file in message.files:
            file.close()


async def test_missing_local_file(tmp_path: Path) -> None:
    """Requirement: V2 messages render into a layout view."""
    missing = tmp_path / "missing.txt"

    with pytest.raises(TemplateError, match=r"missing\.txt"):
        render(tmp_path, V2 + f"components_v2: [{{type: file_display, file_path: '{missing}'}}]\n")


async def test_v1_rows_become_action_rows(tmp_path: Path) -> None:
    """Requirement: V2 messages render into a layout view."""
    rows = "components:\n  - !ButtonsComponent\n    buttons: [{uid: {a: b}, label: Go}]\n"

    message = render(tmp_path, V2 + rows)

    assert layout(message).to_components() == [
        {
            "type": 1,
            "components": [
                {"type": 2, "style": 1, "custom_id": "id:a=b", "label": "Go", "disabled": False}
            ],
        }
    ]
    replaced = render(tmp_path, V2 + rows + "components_v2: [{type: text_display, content: x}]\n")
    assert layout(replaced).to_components() == [{"type": 10, "content": "x"}]


async def test_v2_rows_without_v2_mode(tmp_path: Path) -> None:
    """Requirement: V2 messages render into a layout view."""
    text = (
        "content: Hello\n"
        "components:\n  - !ButtonsComponent\n    buttons: [{uid: {a: old}}]\n"
        "components_v2:\n"
        "  - type: action_row\n"
        "    components: [{type: button, style: RED, custom_id: 'x-%user_name%', label: New}]\n"
    )

    message = render(tmp_path, text)

    assert message.content == "Hello"
    assert type(message.view) is discord.ui.View
    (button,) = message.view.children
    assert isinstance(button, discord.ui.Button)
    assert (button.style, button.custom_id, button.row) == (
        discord.ButtonStyle.danger,
        "x-Alice",
        0,
    )


async def test_untyped_accessories(tmp_path: Path) -> None:
    """Requirement: Section accessories are inferred."""
    text = V2 + (
        "components_v2:\n"
        "  - type: section\n"
        "    components: [{type: text_display, content: a}]\n"
        "    accessory: {url: 'https://e.com/a.png'}\n"
        "  - type: section\n"
        "    content: [{type: text_display, content: b}]\n"
        "    accessory: {uid: {a: b}, label: Go}\n"
    )

    first, second = layout(render(tmp_path, text)).children

    assert isinstance(first, discord.ui.Section)
    assert isinstance(first.accessory, discord.ui.Thumbnail)
    assert isinstance(second, discord.ui.Section)
    assert isinstance(second.accessory, discord.ui.Button)
    assert second.accessory.custom_id == "id:a=b"
    assert [child.to_component_dict() for child in second.children] == [
        {"type": 10, "content": "b"}
    ]


INTERACTIVE = (
    V2
    + """\
components_v2:
  - type: action_row
    components:
      - type: button
        style: GREEN
        uid: {action: "%user_name%"}
        label: "Yes"
        emoji: "<:yes:112233445566778899>"
      - {type: button, style: PREMIUM, sku_id: "123456789012345678", label: ignored}
      - {type: button, style: link, url: "https://e.com", label: Docs}
  - type: action_row
    components:
      - type: string_select_menu
        custom_id: "pick-%user_name%"
        disabled: true
        options:
          - {label: A, value: a, default: true}
          - {label: B, value: b, emoji: "<:b:998877665544332211>"}
        default_values: [b]
  - type: action_row
    components:
      - type: entity_select
        uid: {action: who}
        select_targets: [user, role]
        default_values: [{id: 5, type: role}]
        min: 0
        max: 2
  - type: action_row
    components:
      - type: entity_select
        custom_id: c
        select_target_type: channel
        channel_types: [TEXT, FORUM]
"""
)


async def test_styles_and_ids(tmp_path: Path) -> None:
    """Requirement: V2 interactive components follow v3."""
    buttons, string, mentionable, channel = layout(render(tmp_path, INTERACTIVE)).children

    assert isinstance(buttons, discord.ui.ActionRow)
    success, premium, link = buttons.children
    assert isinstance(success, discord.ui.Button)
    assert (success.style, success.custom_id, success.label) == (
        discord.ButtonStyle.success,
        "id:action=Alice",
        "Yes",
    )
    assert success.emoji == discord.PartialEmoji(name="yes", id=112233445566778899)
    assert isinstance(premium, discord.ui.Button)
    assert (premium.style, premium.sku_id, premium.label) == (
        discord.ButtonStyle.premium,
        123456789012345678,
        None,
    )
    assert isinstance(link, discord.ui.Button)
    assert (link.style, link.url) == (discord.ButtonStyle.link, "https://e.com")

    assert isinstance(string, discord.ui.ActionRow)
    (select,) = string.children
    assert isinstance(select, discord.ui.Select)
    assert (select.custom_id, select.disabled) == ("pick-Alice", True)
    assert [(option.value, option.default) for option in select.options] == [
        ("a", False),
        ("b", True),
    ]
    assert select.options[1].emoji == discord.PartialEmoji(name="b", id=998877665544332211)

    assert isinstance(mentionable, discord.ui.ActionRow)
    (who,) = mentionable.children
    assert isinstance(who, discord.ui.MentionableSelect)
    assert (who.custom_id, who.min_values, who.max_values) == ("id:action=who", 0, 2)
    assert [(value.id, value.type) for value in who.default_values] == [
        (5, discord.SelectDefaultValueType.role)
    ]

    assert isinstance(channel, discord.ui.ActionRow)
    (where,) = channel.children
    assert isinstance(where, discord.ui.ChannelSelect)
    assert where.channel_types == [discord.ChannelType.text, discord.ChannelType.forum]


async def test_disabled_container_and_section(tmp_path: Path) -> None:
    """Requirement: V2 interactive components follow v3."""
    text = V2 + (
        "components_v2:\n"
        "  - type: container\n"
        "    disabled: true\n"
        "    components:\n"
        "      - {type: action_row, components: [{type: button, custom_id: a}]}\n"
        "      - type: action_row\n"
        "        components:\n"
        "          - {type: string_select, custom_id: b, options: [{label: x, value: x}]}\n"
        "      - type: section\n"
        "        components: [{type: text_display, content: t}]\n"
        "        accessory: {type: button, custom_id: c}\n"
        "  - type: section\n"
        "    disabled: true\n"
        "    components: [{type: text_display, content: t}]\n"
        "    accessory: {type: button, custom_id: d}\n"
    )

    view = layout(render(tmp_path, text))

    interactive = [
        item
        for item in view.walk_children()
        if isinstance(item, discord.ui.Button | discord.ui.Select)
    ]
    assert len(interactive) == 4
    assert all(item.disabled for item in interactive)


async def test_uid_needs_an_id_builder(tmp_path: Path) -> None:
    """Requirement: V2 interactive components follow v3."""
    path = tmp_path / "template.yml"
    path.write_text(
        V2 + "components_v2: [{type: action_row, components: [{type: button, uid: {a: b}}]}]\n",
        encoding="utf-8",
    )

    with pytest.raises(TemplateError, match="ID builder"):
        render_message(load_message(path), VALUES)
