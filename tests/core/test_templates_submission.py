"""Requirement: Modal submissions are read back.

Kotlin, where v3 read a modal's input:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:139-145
"""

import pytest

from xincord.core.templates import modal_values


def text_input(custom_id: str, value: str) -> dict[str, object]:
    """A text input as a modal submission carries it."""
    return {"type": 4, "id": 2, "custom_id": custom_id, "value": value}


def test_label_and_action_row_inputs() -> None:
    """Requirement: Modal submissions are read back."""
    data: dict[str, object] = {
        "custom_id": "feedback:1:a=submit_form;c=3;d=6",
        "components": [
            {"type": 18, "id": 1, "component": text_input("form", "great")},
            {"type": 1, "id": 3, "components": [text_input("title", "")]},
            {"type": 10, "id": 4, "content": "Thanks"},
        ],
    }

    assert modal_values(data) == {"form": "great", "title": ""}


def test_other_components_are_skipped() -> None:
    """Requirement: Modal submissions are read back."""
    select = {"type": 3, "id": 2, "custom_id": "pick", "values": ["a"]}
    data: dict[str, object] = {"components": [{"type": 18, "id": 1, "component": select}]}

    assert modal_values(data) == {}


@pytest.mark.parametrize("data", [None, {}, {"components": "broken"}])
def test_no_inputs(data: dict[str, object] | None) -> None:
    """Requirement: Modal submissions are read back."""
    assert modal_values(data) == {}
