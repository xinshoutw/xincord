"""Requirement: Commit messages are ASCII Conventional Commits."""

from typing import TYPE_CHECKING

import pytest

from check_commit_msg import main, problems

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Commit messages are ASCII Conventional Commits",
)

IDEOGRAPH = chr(0x4E2D)
FULL_STOP = chr(0x3002)
SCISSORS = "# ------------------------ >8 ------------------------"


@pytest.mark.parametrize(
    "message",
    [
        "feat(plugin-auto-role): assign roles on join\n\n- add the listener\n- add the config\n",
        "docs: describe the gate\n",
        "fix(core)!: drop the legacy flag\n",
    ],
)
def test_valid_message_is_accepted(message: str) -> None:
    assert problems(message) == []


@pytest.mark.parametrize(
    ("message", "line"),
    [
        (f"fix(core): handle {IDEOGRAPH}\n", 1),
        (f"fix(core): handle input\n\n- reject {FULL_STOP}\n", 3),
    ],
)
def test_non_ascii_text_is_rejected(message: str, line: int) -> None:
    found = problems(message)

    assert len(found) == 1
    assert f"line {line}" in found[0]


@pytest.mark.parametrize(
    "message",
    [
        "feature(core): add x\n",
        "feat(Core): add x\n",
        "feat(plugin_auto_role): add x\n",
        "feat(plugin-): add x\n",
        "feat(core) add x\n",
        "feat(core):add x\n",
        "Feat: add x\n",
        "\n",
    ],
)
def test_unknown_type_or_scope_is_rejected(message: str) -> None:
    assert problems(message)


def test_comments_and_the_verbose_diff_are_ignored() -> None:
    message = (
        f"# leading comment {IDEOGRAPH}\n"
        "docs: update the guide\n"
        f"# Please enter the commit message {FULL_STOP}\n"
        f"{SCISSORS}\n"
        "diff --git a/x b/x\n"
        f"+{IDEOGRAPH}\n"
    )

    assert problems(message) == []


def test_hook_exit_status_reflects_the_check(tmp_path: Path) -> None:
    good = tmp_path / "good"
    good.write_text("chore: tidy\n", encoding="utf-8")
    bad = tmp_path / "bad"
    bad.write_text("tidy\n", encoding="utf-8")

    assert main(["check_commit_msg", str(good)]) == 0
    assert main(["check_commit_msg", str(bad)]) == 1
