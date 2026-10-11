"""Requirement: Templates are validated when they load."""

import logging
from typing import TYPE_CHECKING

import pytest

from xincord.core.i18n import Lang
from xincord.core.templates import TemplateError, Templates, load_message, load_modal

if TYPE_CHECKING:
    from pathlib import Path

VALID = """\
content: "Hello %user_name%"
embeds:
  - title:
      text: "Title"
      url: "https://example.com"
    description: "Body"
    color_code: "#9bd9d5"
    timestamp: "%now%"
    fields:
      - name: "Name"
        value: "Value"
        inline: true
      - model_key: "extra_field"
components:
  - !ButtonsComponent
    buttons:
      - style: 5
        url: "https://example.com"
        label: "Open"
      - uid: {action: "join", id: 123}
        label: "Join"
        emoji: {formatted: "<:join:111>"}
  - !EntitySelectMenu
    uid: {action: "pick"}
    select_target_type: "CHANNEL"
    channel_types: ["TEXT", "NEWS"]
  - !StringSelectMenu
    uid: {action: "choose"}
    options:
      - label: "One"
        value: "1"
"""

MODAL = """\
uid: {action: "feedback"}
title: "Feedback"
text_inputs:
  - uid: "content"
    label: "Content"
    style: PARAGRAPH
    max_length: 200
"""


def write(tmp_path: Path, text: str, name: str = "template.yml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_template_loads(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        load_message(write(tmp_path, VALID))
        load_modal(write(tmp_path, MODAL, "modal.yml"))

    assert caplog.records == []


@pytest.mark.parametrize(
    "text",
    [
        "content: [unclosed\n",
        "- a list\n",
        "components:\n  - !Unknown {}\n",
        "components:\n  - !ButtonsComponent\n    buttons:\n      - {style: 9, uid: {a: b}}\n",
        "components:\n  - !ButtonsComponent\n    buttons:\n      - {style: 5, label: x}\n",
        "components:\n  - !ButtonsComponent\n    buttons:\n      - {style: 1, label: x}\n",
        "components:\n  - !ButtonsComponent\n    buttons:\n      - {uid: {a: b}, emoji: {}}\n",
        "components:\n  - !EntitySelectMenu\n    uid: {a: b}\n    select_target_type: CHANNEL\n",
        "components:\n  - !EntitySelectMenu\n    uid: {a: b}\n    select_target_type: GUILD\n",
        (
            "components:\n  - !EntitySelectMenu\n    uid: {a: b}\n"
            "    select_target_type: CHANNEL\n    channel_types: [TXT]\n"
        ),
        "components:\n  - !StringSelectMenu\n    options: [{label: a, value: b}]\n",
        "embeds:\n  - timestamp: yesterday\n",
        "embeds:\n  - color_code: red\n",
        "embeds:\n  - fields: [{name: only-a-name}]\n",
        "components:\n  - !ButtonsComponent [a]\n",
        (
            "components:\n  - !StringSelectMenu\n    uid: {a: b}\n"
            "    options: [{label: a, value: b, emoji: {animated: true}}]\n"
        ),
    ],
)
def test_invalid_template_fails(tmp_path: Path, text: str) -> None:
    path = write(tmp_path, text)

    with pytest.raises(TemplateError, match=str(path)):
        load_message(path)


@pytest.mark.parametrize(
    "text",
    [
        "title: x\n",
        "uid: {a: b}\ntitle: x\ntext_inputs: [{uid: c, label: d, style: LONG}]\n",
    ],
)
def test_invalid_modal_fails(tmp_path: Path, text: str) -> None:
    path = write(tmp_path, text)

    with pytest.raises(TemplateError, match=str(path)):
        load_modal(path)


def test_model_keys_skip_required_fields(tmp_path: Path) -> None:
    text = (
        "components:\n"
        "  - !EntitySelectMenu {model_key: picker}\n"
        "  - !ButtonsComponent\n    buttons: [{model_key: join}]\n"
    )

    load_message(write(tmp_path, text))


def test_unknown_key_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = write(tmp_path, 'embeds:\n  - description: "x"\n    colour_code: "#ffffff"\n')

    with caplog.at_level(logging.WARNING):
        load_message(path)

    messages = [record.getMessage() for record in caplog.records]
    assert any(str(path) in message and "embeds.0.colour_code" in message for message in messages)


def lang(tmp_path: Path, files: dict[str, str]) -> Lang:
    for relative, text in files.items():
        path = tmp_path / "lang" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Lang.load("Example", tmp_path / "lang", "en-US")


def test_plugin_templates_load_for_every_locale(tmp_path: Path) -> None:
    files = {
        "en-US/message/greet.yml": 'content: "hello"\n',
        "zh-TW/message/greet.yml": 'content: "hi"\n',
        "en-US/modal/ask.yml": MODAL,
    }

    templates = Templates.load(lang(tmp_path, files))

    assert templates.message("greet", "zh-TW") != templates.message("greet", "en-US")
    assert templates.message("greet", "ja") == templates.message("greet", "en-US")
    assert templates.modal("ask", "zh-TW") == templates.modal("ask", "en-US")


def test_broken_template_in_any_locale_fails(tmp_path: Path) -> None:
    files = {
        "en-US/message/greet.yml": 'content: "hello"\n',
        "zh-TW/message/greet.yml": "embeds:\n  - timestamp: soon\n",
    }

    with pytest.raises(TemplateError, match=r"zh-TW"):
        Templates.load(lang(tmp_path, files))
