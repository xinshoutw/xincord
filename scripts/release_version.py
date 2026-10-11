"""Print the version that a release tag must name: the one both distributions declare.

Usage: release_version.py [TAG]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROJECTS = ("pyproject.toml", "packages/xincord-plugins/pyproject.toml")


def release_version(root: Path, tag: str | None = None) -> str:
    """Return both distributions' version; fail when they differ or ``tag`` names another."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    """Print the version, or the error and exit 1."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
