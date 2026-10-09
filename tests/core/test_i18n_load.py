"""Lang loading: locales, validation and key sets.

Kotlin: XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/localizations/StringLocalizer.kt:32-67.
"""

import logging
from typing import TYPE_CHECKING

import pytest

from xincord.core.i18n import Lang, LangError

if TYPE_CHECKING:
    from pathlib import Path


def xfail(requirement: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=requirement)


LOCALES = xfail("Locales come from Discord locale directories")
VALIDATED = xfail("Lang files are validated at load")
KEY_SETS = xfail("Key sets are compared with the default locale")

REGISTER = "calc:\n  name: calc\n  description: Calculate\n"


def lang_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = tmp_path / "lang" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path / "lang"


def load(tmp_path: Path, files: dict[str, str]) -> Lang:
    return Lang.load("Calc", lang_dir(tmp_path, files), "en-US")


@LOCALES
def test_unknown_directory_is_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    files = {f"{name}/register.yaml": REGISTER for name in ("en-US", "zh-TW", "backup")}

    with caplog.at_level(logging.WARNING):
        lang = load(tmp_path, files)

    assert lang.locales == ("en-US", "zh-TW")
    assert any("backup" in record.getMessage() for record in caplog.records)


@LOCALES
def test_default_locale_is_required(tmp_path: Path) -> None:
    with pytest.raises(LangError, match=r"Calc.*en-US"):
        load(tmp_path, {"zh-TW/register.yaml": REGISTER})


@VALIDATED
@pytest.mark.parametrize(
    ("text", "key"),
    [("calc:\n  name: [a]\n", "calc.name"), ("calc:\n  count: 3\n", "calc.count")],
)
def test_non_string_leaf_fails(tmp_path: Path, text: str, key: str) -> None:
    with pytest.raises(LangError, match=rf"register\.yaml.*{key}"):
        load(tmp_path, {"en-US/register.yaml": text})


@VALIDATED
@pytest.mark.parametrize("text", ["calc: [unclosed\n", "- a list\n"])
def test_broken_file_fails(tmp_path: Path, text: str) -> None:
    with pytest.raises(LangError, match=r"placeholder\.yaml"):
        load(tmp_path, {"en-US/register.yaml": REGISTER, "en-US/placeholder.yaml": text})


@VALIDATED
@pytest.mark.parametrize("name", ["Calc", "my calc", "x" * 33, ""])
def test_invalid_command_name_fails(tmp_path: Path, name: str) -> None:
    with pytest.raises(LangError, match=r"calc\.name"):
        load(tmp_path, {"en-US/register.yaml": f'calc:\n  name: "{name}"\n'})


@VALIDATED
@pytest.mark.parametrize("name", ["calc", "my-calc_2", "o'clock", chr(0x8A08) + chr(0x7B97)])
def test_valid_command_names_load(tmp_path: Path, name: str) -> None:
    lang = load(tmp_path, {"en-US/register.yaml": f'calc:\n  name: "{name}"\n'})

    assert lang.registers["en-US"]["calc.name"] == name


@VALIDATED
@pytest.mark.parametrize("description", ["", "x" * 101])
def test_description_length_is_checked(tmp_path: Path, description: str) -> None:
    with pytest.raises(LangError, match=r"calc\.description"):
        load(tmp_path, {"en-US/register.yaml": f'calc:\n  description: "{description}"\n'})


@VALIDATED
def test_duplicate_template_fails(tmp_path: Path) -> None:
    files = {
        "en-US/register.yaml": REGISTER,
        "en-US/message/result.yml": "content: a\n",
        "en-US/message/result.yaml": "content: b\n",
    }

    with pytest.raises(LangError, match=r"message/result"):
        load(tmp_path, files)


@KEY_SETS
def test_missing_and_extra_keys_warn(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
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
