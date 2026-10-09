"""commit-msg hook: accept only ASCII Conventional Commits (see AGENTS.md)."""

import re
import sys
from pathlib import Path

TYPES = "feat|fix|test|refactor|docs|build|ci|chore"
SCOPES = "core|build|ci|docs|plugin(?:-[a-z0-9]+)+"
SUBJECT = re.compile(rf"(?:{TYPES})(?:\((?:{SCOPES})\))?!?: \S")
SCISSORS = "# ------------------------ >8 ------------------------"
ATTRIBUTION = re.compile(
    r"^(?:co-authored-by|claude-session):|generated with \[claude code\]",
    re.IGNORECASE,
)


def problems(message: str) -> list[str]:
    """Return what is wrong with a commit message; an empty list means it is acceptable."""
    lines = message.split("\n")
    if SCISSORS in lines:
        lines = lines[: lines.index(SCISSORS)]
    numbered = [(n, line) for n, line in enumerate(lines, 1) if not line.startswith("#")]

    found = [f"line {n}: non-ASCII text" for n, line in numbered if not line.isascii()]
    found += [f"line {n}: tool attribution" for n, line in numbered if ATTRIBUTION.search(line)]
    subject = next(((n, line) for n, line in numbered if line.strip()), (1, ""))
    if not SUBJECT.match(subject[1]):
        found.append(
            f"line {subject[0]}: expected 'type(scope): subject' with type in {TYPES} "
            f"and an optional scope of core, build, ci, docs or plugin-<name>",
        )
    return found


def main(argv: list[str]) -> int:
    found = problems(Path(argv[1]).read_text(encoding="utf-8"))
    for problem in found:
        print(problem, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
