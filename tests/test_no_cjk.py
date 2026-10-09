"""Requirement: Python sources contain no CJK characters."""

import re
from pathlib import Path

import pytest
import yaml

CONFIG = Path(__file__).parent.parent / ".pre-commit-config.yaml"


def flags(text: str) -> bool:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    (hook,) = [hook for hook in hooks if hook["id"] == "no-cjk-in-python"]
    assert hook["language"] == "pygrep"
    assert hook["types"] == ["python"]
    # prek, like pre-commit, compiles pygrep patterns as bytes.
    pattern = re.compile(hook["entry"].encode())
    return pattern.search(f'x = "{text}"\n'.encode()) is not None


@pytest.mark.parametrize("code_point", [0x4E2D, 0x3042, 0xF900, 0x20000])
def test_cjk_ideograph_is_rejected(code_point: int) -> None:
    assert flags(chr(code_point))


@pytest.mark.parametrize("code_point", [0xFF0C, 0x3002])
def test_fullwidth_punctuation_is_rejected(code_point: int) -> None:
    assert flags(chr(code_point))


@pytest.mark.parametrize("text", ["plain", "caf" + chr(0xE9), chr(0x1F600), chr(0x2014)])
def test_other_text_passes(text: str) -> None:
    assert not flags(text)
