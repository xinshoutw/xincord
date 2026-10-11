"""Requirement: V2 model keys insert runtime objects."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.templates import Message, TemplateError, load_message, render_message

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

V2 = "is_components_v2: true\n"
BULLET = chr(0x2022)


def render(tmp_path: Path, text: str, models: Mapping[str, object]) -> Message:
    path = tmp_path / "template.yml"
    path.write_text(text, encoding="utf-8")
    return render_message(load_message(path), {}, models=models)


def children(message: Message) -> list[discord.ui.Item[discord.ui.LayoutView]]:
    assert isinstance(message.view, discord.ui.LayoutView)
    return message.view.children


async def test_embed_model_as_a_container(tmp_path: Path) -> None:
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    embed = discord.Embed(
        title="Title",
        url="https://e.com/t",
        description="Body",
        colour=0x123456,
        timestamp=moment,
    )
    embed.set_author(name="Author", url="https://e.com/a", icon_url="https://e.com/icon.png")
    embed.add_field(name="Name", value="Value")
    embed.add_field(name=" ", value="Only value")
    embed.set_image(url="https://e.com/image.png")
    embed.set_footer(text="Footer")

    (container,) = children(
        render(tmp_path, V2 + "components_v2: [{model_key: board}]\n", {"board": embed})
    )

    assert container.to_component_dict() == {
        "type": 17,
        "accent_color": 0x123456,
        "spoiler": False,
        "components": [
            {
                "type": 9,
                "components": [
                    {
                        "type": 10,
                        "content": "### [Author](https://e.com/a)\n## [Title](https://e.com/t)\nBody",
                    }
                ],
                "accessory": {
                    "type": 11,
                    "media": {"url": "https://e.com/icon.png"},
                    "description": None,
                    "spoiler": False,
                },
            },
            {"type": 10, "content": "**Name**\nValue"},
            {"type": 10, "content": "Only value"},
            {
                "type": 12,
                "items": [{"media": {"url": "https://e.com/image.png"}, "spoiler": False}],
            },
            {"type": 14, "divider": True, "spacing": 1},
            {"type": 10, "content": f"*Footer {BULLET} <t:{int(moment.timestamp())}:f>*"},
        ],
    }


@pytest.mark.parametrize(
    ("embed", "texts"),
    [
        (discord.Embed(), ["_ _"]),
        (discord.Embed().add_field(name=" ", value=" "), ["_ _"]),
        (discord.Embed(title="Plain"), ["## Plain"]),
        (discord.Embed().set_footer(text="Only footer"), ["*Only footer*"]),
    ],
)
async def test_sparse_embed_models(tmp_path: Path, embed: discord.Embed, texts: list[str]) -> None:
    (container,) = children(
        render(tmp_path, V2 + "components_v2: [{model_key: e}]\n", {"e": embed})
    )

    assert isinstance(container, discord.ui.Container)
    assert [child.to_component_dict() for child in container.children] == [
        {"type": 10, "content": text} for text in texts
    ]
    assert container.accent_colour is None


async def test_models_at_every_level(tmp_path: Path) -> None:
    text = (
        V2
        + """\
components_v2:
  - {model_key: intro}
  - type: container
    components:
      - {model_key: rule}
      - type: section
        components: [{model_key: line}]
        accessory: {model_key: pic}
      - type: action_row
        components:
          - {model_key: go}
          - {type: button, custom_id: x, emoji: {model_key: smile}}
  - type: action_row
    components: [{type: string_select, custom_id: s, options: [{model_key: opt}]}]
  - {type: media_gallery, items: [{model_key: shot}]}
"""
    )
    models: dict[str, object] = {
        "intro": discord.ui.TextDisplay[discord.ui.LayoutView]("intro"),
        "rule": discord.ui.Separator[discord.ui.LayoutView](),
        "line": discord.ui.TextDisplay[discord.ui.LayoutView]("line"),
        "pic": discord.ui.Thumbnail[discord.ui.LayoutView]("https://e.com/p.png"),
        "go": discord.ui.Button[discord.ui.LayoutView](custom_id="go"),
        "smile": discord.PartialEmoji(name="smile", id=112233445566778899),
        "opt": discord.SelectOption(label="o", value="o"),
        "shot": discord.MediaGalleryItem("https://e.com/s.png"),
    }

    intro, container, row, gallery = children(render(tmp_path, text, models))

    assert intro is models["intro"]
    assert isinstance(container, discord.ui.Container)
    rule, section, buttons = container.children
    assert rule is models["rule"]
    assert isinstance(section, discord.ui.Section)
    assert section.children == [models["line"]]
    assert section.accessory is models["pic"]
    assert isinstance(buttons, discord.ui.ActionRow)
    go, smile = buttons.children
    assert go is models["go"]
    assert isinstance(smile, discord.ui.Button)
    assert smile.emoji == models["smile"]
    assert isinstance(row, discord.ui.ActionRow)
    (select,) = row.children
    assert isinstance(select, discord.ui.Select)
    assert select.options == [models["opt"]]
    assert isinstance(gallery, discord.ui.MediaGallery)
    assert gallery.items == [models["shot"]]


@pytest.mark.parametrize(
    "entry",
    [
        "{model_key: bad}",
        "{type: section, components: [{model_key: bad}], accessory: {type: button, custom_id: a}}",
        (
            "{type: section, components: [{type: text_display, content: a}],"
            " accessory: {model_key: bad}}"
        ),
        "{type: action_row, components: [{model_key: bad}]}",
        "{type: action_row, components: [{type: button, custom_id: a, emoji: {model_key: bad}}]}",
        (
            "{type: action_row, components: [{type: string_select, custom_id: a,"
            " options: [{model_key: bad}]}]}"
        ),
        "{type: media_gallery, items: [{model_key: bad}]}",
    ],
)
@pytest.mark.parametrize("models", [{}, {"bad": 42}])
async def test_missing_or_wrong_models(
    tmp_path: Path, entry: str, models: dict[str, object]
) -> None:
    with pytest.raises(TemplateError, match="bad"):
        render(tmp_path, V2 + f"components_v2:\n  - {entry}\n", models)
