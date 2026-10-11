"""Requirement: Modal templates render text inputs."""

from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.templates import TemplateError, load_modal, render_modal

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

MODAL = """\
uid: {action: "feedback", who: "%user_name%"}
title: "Feedback from %user_name%"
text_inputs:
  - uid: "subject"
    label: "Subject"
    style: SHORT
    max_length: 20
    placeholder: "About %user_name%"
  - uid: "body"
    label: "Body"
    style: PARAGRAPH
    value: "%blank%"
    required: false
    min_length: 0
"""


def build_id(uid: Mapping[str, str]) -> str:
    return "modal:" + ",".join(f"{key}={value}" for key, value in uid.items())


def render(
    tmp_path: Path,
    text: str,
    models: Mapping[str, object] | None = None,
) -> discord.ui.Modal:
    path = tmp_path / "modal.yml"
    path.write_text(text, encoding="utf-8")
    values = {"user_name": "Alice", "blank": "  "}
    return render_modal(load_modal(path), values, build_id=build_id, models=models)


async def test_modal_with_two_inputs(tmp_path: Path) -> None:
    modal = render(tmp_path, MODAL)

    assert (modal.title, modal.custom_id) == (
        "Feedback from Alice",
        "modal:action=feedback,who=Alice",
    )
    subject_label, body_label = modal.children
    assert isinstance(subject_label, discord.ui.Label)
    assert isinstance(body_label, discord.ui.Label)
    assert (subject_label.text, body_label.text) == ("Subject", "Body")
    subject, body = subject_label.component, body_label.component
    assert isinstance(subject, discord.ui.TextInput)
    assert isinstance(body, discord.ui.TextInput)
    assert (subject.custom_id, subject.style) == ("subject", discord.TextStyle.short)
    assert (subject.max_length, subject.min_length, subject.required) == (20, None, True)
    assert (subject.placeholder, subject.default) == ("About Alice", None)
    assert (body.style, body.default, body.required, body.min_length) == (
        discord.TextStyle.paragraph,
        None,
        False,
        0,
    )
    assert modal.is_finished()


async def test_modal_model_keys(tmp_path: Path) -> None:
    prebuilt = discord.ui.Modal(title="prebuilt", custom_id="p")
    field = discord.ui.TextInput[discord.ui.Modal](custom_id="m")
    text = 'uid: {a: b}\ntitle: "t"\ntext_inputs: [{model_key: "input", label: "L"}]\n'

    assert render(tmp_path, "model_key: whole\n", {"whole": prebuilt}) is prebuilt
    (label,) = render(tmp_path, text, {"input": field}).children
    assert isinstance(label, discord.ui.Label)
    assert label.component is field

    with pytest.raises(TemplateError, match="input"):
        render(tmp_path, text, {"input": "not a text input"})


async def test_modal_needs_an_id_builder(tmp_path: Path) -> None:
    path = tmp_path / "modal.yml"
    path.write_text(MODAL, encoding="utf-8")

    with pytest.raises(TemplateError, match="ID builder"):
        render_modal(load_modal(path), {}, build_id=None)
