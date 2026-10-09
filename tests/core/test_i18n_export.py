"""Requirement: Bundled lang files are exported.

Kotlin: XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:24-37.
"""

from typing import TYPE_CHECKING

import pytest

from xincord.core.i18n import export_lang

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Bundled lang files are exported",
)

BUNDLED = {
    "en-US/register.yaml": "calc:\n  name: calc\n",
    "zh-TW/register.yaml": "calc:\n  name: calc\n",
    "zh-TW/message/result.yml": "content: done\n",
}


def bundle(root: Path) -> Path:
    for relative, text in BUNDLED.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_first_export_writes_every_file(tmp_path: Path) -> None:
    target = tmp_path / "plugins" / "Calc" / "lang"

    written = export_lang(bundle(tmp_path / "bundled"), target, force=False)

    assert sorted(written) == sorted(target / relative for relative in BUNDLED)
    for relative, text in BUNDLED.items():
        assert (target / relative).read_text(encoding="utf-8") == text


def test_operator_edits_are_kept(tmp_path: Path) -> None:
    target = tmp_path / "lang"
    (target / "en-US").mkdir(parents=True)
    (target / "en-US" / "register.yaml").write_text("edited\n", encoding="utf-8")

    written = export_lang(bundle(tmp_path / "bundled"), target, force=False)

    assert (target / "en-US" / "register.yaml").read_text(encoding="utf-8") == "edited\n"
    assert target / "en-US" / "register.yaml" not in written
    assert (target / "zh-TW" / "message" / "result.yml").exists()


def test_forced_renewal_overwrites_bundled_files_only(tmp_path: Path) -> None:
    target = tmp_path / "lang"
    (target / "en-US").mkdir(parents=True)
    (target / "en-US" / "register.yaml").write_text("edited\n", encoding="utf-8")
    (target / "en-US" / "custom.yaml").write_text("mine: yes\n", encoding="utf-8")

    export_lang(bundle(tmp_path / "bundled"), target, force=True)

    assert (target / "en-US" / "register.yaml").read_text(encoding="utf-8") == BUNDLED[
        "en-US/register.yaml"
    ]
    assert (target / "en-US" / "custom.yaml").read_text(encoding="utf-8") == "mine: yes\n"
