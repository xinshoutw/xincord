"""Requirement: Components V2 templates are validated when they load."""

import logging
from pathlib import Path

import pytest

from xincord.core.templates import TemplateError, load_message

EXAMPLE = Path(__file__).parent.parent / "fixtures" / "templates" / "components_v2_example.yml"
TEXT = "{type: text_display, content: a}"


def test_valid_v2_template_loads(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        load_message(EXAMPLE)

    assert caplog.records == []


def test_type_names_are_normalized(tmp_path: Path) -> None:
    path = tmp_path / "template.yml"
    path.write_text(
        "is_components_v2: true\n"
        "components_v2:\n"
        "  - {type: Text-Display, content: a}\n"
        "  - type: ACTION_ROW\n"
        "    components:\n"
        "      - {type: string-select-menu, custom_id: x, options: [{label: a, value: b}]}\n",
        encoding="utf-8",
    )

    load_message(path)


@pytest.mark.parametrize(
    "text",
    [
        f"is_components_v2: true\ncontent: x\ncomponents_v2: [{TEXT}]\n",
        f"is_components_v2: true\nembeds: [{{description: x}}]\ncomponents_v2: [{TEXT}]\n",
        "is_components_v2: true\n",
        (
            "components_v2: [{type: section, components: [" + TEXT + "],"
            " accessory: {url: 'https://example.com/a.png'}}]\n"
        ),
        "components_v2: [{model_key: row}]\n",
        "is_components_v2: true\ncomponents_v2: [{type: carousel}]\n",
        "is_components_v2: true\ncomponents_v2: [{type: text_display}]\n",
        (
            "is_components_v2: true\ncomponents_v2:\n"
            "  - {type: action_row, components: [{type: button, label: x}]}\n"
        ),
        (
            "is_components_v2: true\ncomponents_v2:\n"
            "  - {type: action_row, components: [{type: button, style: PREMIUM}]}\n"
        ),
        (
            "is_components_v2: true\ncomponents_v2:\n"
            "  - {type: action_row, components: [{type: entity_select, custom_id: x}]}\n"
        ),
        (
            "is_components_v2: true\ncomponents_v2:\n"
            "  - {type: action_row, components: [{type: button, style: PINK, custom_id: x}]}\n"
        ),
    ],
)
def test_v2_mode_rules(tmp_path: Path, text: str) -> None:
    path = tmp_path / "template.yml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(TemplateError, match=str(path)):
        load_message(path)


def test_model_keys_and_variants_load(tmp_path: Path) -> None:
    path = tmp_path / "template.yml"
    path.write_text(
        "is_components_v2: true\n"
        "components_v2:\n"
        "  - {model_key: header}\n"
        "  - {type: section, content: [{model_key: text}], accessory: {model_key: button}}\n"
        "  - type: action_row\n"
        "    components:\n"
        "      - {type: button, custom_id: a, emoji: {name: x}}\n"
        "      - type: entity_select\n"
        "        custom_id: b\n"
        "        select_target_type: user\n"
        "        default_values: [{id: 1, type: user}]\n"
        "  - {type: media_gallery, items: [{model_key: item}, {file_name: a.png}]}\n"
        "  - {type: container, accent_color: 255}\n"
        "  - {type: container, accent_color: '255'}\n"
        "  - {type: container, accent_color: '0xff'}\n",
        encoding="utf-8",
    )

    template = load_message(path)

    assert len(template.components_v2) == 7
    containers = template.components_v2[4:]
    assert [getattr(container, "accent_color", None) for container in containers] == [255] * 3


V2 = "is_components_v2: true\ncomponents_v2:\n  - "


@pytest.mark.parametrize(
    "entry",
    [
        "text",
        "{type: action_row, components: [{type: button, custom_id: a, emoji: {}}]}",
        "{type: action_row, components: [{type: string_select}]}",
        (
            "{type: action_row, components: [{type: entity_select, custom_id: a,"
            " select_targets: [USER], default_values: [{id: 1, type: guild}]}]}"
        ),
        (
            "{type: action_row, components: [{type: entity_select, custom_id: a,"
            " select_targets: [CHANNEL], channel_types: [ATTIC]}]}"
        ),
        "{type: media_gallery, items: [{description: x}]}",
        "{type: separator, spacing: HUGE}",
        "{type: file_display}",
        "{type: container, accent_color: blue}",
        "{type: action_row, components: [{type: button, style: 6, sku: premium}]}",
        (
            "{type: action_row, components: [{type: entity_select, custom_id: a,"
            " select_targets: [ROLE], default_values: [{id: admin, type: role}]}]}"
        ),
    ],
)
def test_invalid_components(tmp_path: Path, entry: str) -> None:
    path = tmp_path / "template.yml"
    path.write_text(V2 + entry + "\n", encoding="utf-8")

    with pytest.raises(TemplateError, match=str(path)):
        load_message(path)
