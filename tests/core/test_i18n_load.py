"""Lang loading: locales, validation and key sets.

Kotlin: XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/localizations/StringLocalizer.kt:32-67.
"""

import logging
from typing import TYPE_CHECKING

import pytest

from xincord.core.i18n import Lang, LangError, is_command_name

if TYPE_CHECKING:
    from pathlib import Path


REGISTER = "calc:\n  name: calc\n  description: Calculate\n"
VALID_NAMES = ["calc", "my-calc_2", "o'clock", chr(0x8A08) + chr(0x7B97)]
INVALID_NAMES = ["Calc", "my calc", "x" * 33, ""]


def lang_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = tmp_path / "lang" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path / "lang"


def load(tmp_path: Path, files: dict[str, str]) -> Lang:
    return Lang.load("Calc", lang_dir(tmp_path, files), "en-US")


def test_unknown_directory_is_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Locales come from Discord locale directories."""

    files = {f"{name}/register.yaml": REGISTER for name in ("en-US", "zh-TW", "backup")}

    with caplog.at_level(logging.WARNING):
        lang = load(tmp_path, files)

    assert lang.locales == ("en-US", "zh-TW")
    assert any("backup" in record.getMessage() for record in caplog.records)


def test_default_locale_is_required(tmp_path: Path) -> None:
    """Requirement: Locales come from Discord locale directories."""

    with pytest.raises(LangError, match=r"Calc.*en-US"):
        load(tmp_path, {"zh-TW/register.yaml": REGISTER})


@pytest.mark.parametrize(
    ("text", "key"),
    [("calc:\n  name: [a]\n", "calc.name"), ("calc:\n  count: 3\n", "calc.count")],
)
def test_non_string_leaf_fails(tmp_path: Path, text: str, key: str) -> None:
    """Requirement: Lang files are validated at load."""

    with pytest.raises(LangError, match=rf"register\.yaml.*{key}"):
        load(tmp_path, {"en-US/register.yaml": text})


@pytest.mark.parametrize("text", ["calc: [unclosed\n", "- a list\n"])
def test_broken_file_fails(tmp_path: Path, text: str) -> None:
    """Requirement: Lang files are validated at load."""

    with pytest.raises(LangError, match=r"placeholder\.yaml"):
        load(tmp_path, {"en-US/register.yaml": REGISTER, "en-US/placeholder.yaml": text})


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_invalid_command_name_fails(tmp_path: Path, name: str) -> None:
    """Requirement: Lang files are validated at load."""

    with pytest.raises(LangError, match=r"calc\.name"):
        load(tmp_path, {"en-US/register.yaml": f'calc:\n  name: "{name}"\n'})


@pytest.mark.parametrize("name", VALID_NAMES)
def test_valid_command_names_load(tmp_path: Path, name: str) -> None:
    """Requirement: Lang files are validated at load."""

    lang = load(tmp_path, {"en-US/register.yaml": f'calc:\n  name: "{name}"\n'})

    assert lang.registers["en-US"]["calc.name"] == name


@pytest.mark.parametrize("name", VALID_NAMES)
def test_public_name_check_accepts(name: str) -> None:
    """Requirement: Lang files are validated at load."""

    assert is_command_name(name)


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_public_name_check_refuses(name: str) -> None:
    """Requirement: Lang files are validated at load."""

    assert not is_command_name(name)


@pytest.mark.parametrize("description", ["", "x" * 101])
def test_description_length_is_checked(tmp_path: Path, description: str) -> None:
    """Requirement: Lang files are validated at load."""

    with pytest.raises(LangError, match=r"calc\.description"):
        load(tmp_path, {"en-US/register.yaml": f'calc:\n  description: "{description}"\n'})


def test_duplicate_template_fails(tmp_path: Path) -> None:
    """Requirement: Lang files are validated at load."""

    files = {
        "en-US/register.yaml": REGISTER,
        "en-US/message/result.yml": "content: a\n",
        "en-US/message/result.yaml": "content: b\n",
    }

    with pytest.raises(LangError, match=r"message/result"):
        load(tmp_path, files)


def test_missing_and_extra_keys_warn(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Key sets are compared with the default locale."""

    files = {
        "en-US/register.yaml": "a:\n  name: a\n  description: A\n",
        "zh-TW/register.yaml": "a:\n  name: a\nb:\n  name: b\n",
    }

    with caplog.at_level(logging.WARNING):
        load(tmp_path, files)

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 2
    assert any("zh-TW" in message and "a.description" in message for message in messages)
    assert any("zh-TW" in message and "b.name" in message for message in messages)


def test_stray_files_are_ignored(tmp_path: Path) -> None:
    """Requirement: Locales come from Discord locale directories."""

    files = {
        "README.md": "notes\n",
        "en-US/register.yaml": REGISTER,
        "en-US/empty.yaml": "",
        "en-US/message/result.yml": "content: a\n",
        "en-US/message/notes.txt": "draft\n",
    }

    lang = load(tmp_path, files)

    assert lang.locales == ("en-US",)
    assert list(lang.templates["en-US"]) == ["message/result"]
    assert lang.texts["en-US"] == {}
