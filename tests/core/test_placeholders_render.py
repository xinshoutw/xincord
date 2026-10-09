"""Placeholder rendering.

Kotlin: XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Substitutor.kt:80-93.
"""

import pytest

from xincord.core.placeholders import render


def test_known_and_unknown_keys() -> None:
    """Requirement: Placeholders are replaced in a single pass."""

    assert render("Hi %user_name%, %missing%!", {"user_name": "Alice"}) == "Hi Alice, %missing%!"


def test_values_are_not_expanded_again() -> None:
    """Requirement: Placeholders are replaced in a single pass."""

    values = {"user_name": "%bot_name%", "bot_name": "xincord"}

    assert render("%user_name% / %bot_name%", values) == "%bot_name% / xincord"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("100% of %user_name%", "100% of Alice"),
        ("$%user_name%", "%user_name%"),
        ("$%user_name% %user_name%", "%user_name% Alice"),
        ("$$%user_name%", "$%user_name%"),
        ("%%user_name%", "%Alice"),
        ("50%", "50%"),
        ("%user_name%%user_name%", "AliceAlice"),
        ("", ""),
    ],
)
def test_percent_signs_and_escapes(text: str, expected: str) -> None:
    """Requirement: Placeholders are replaced in a single pass."""

    assert render(text, {"user_name": "Alice"}) == expected


def test_values_do_not_leak_between_renders() -> None:
    """Requirement: Every render uses only its own values."""

    values = {"extra": "x"}

    assert render("%extra%", values) == "x"
    assert render("%extra%", {}) == "%extra%"
    assert values == {"extra": "x"}
