"""commit-msg hook: accept only ASCII Conventional Commits (see AGENTS.md)."""

import sys
from pathlib import Path


def problems(message: str) -> list[str]:
    """Return what is wrong with a commit message; an empty list means it is acceptable."""
    raise NotImplementedError


def main(argv: list[str]) -> int:
    found = problems(Path(argv[1]).read_text(encoding="utf-8"))
    for problem in found:
        print(problem, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
