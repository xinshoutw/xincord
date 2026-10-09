"""Requirement: Components V2 templates are validated when they load.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/builder/MessageBuilder.kt:9-57
"""

import logging
from pathlib import Path

import pytest

from xincord.core.templates import TemplateError, load_message

pytestmark = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Components V2 templates are validated when they load",
)

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
