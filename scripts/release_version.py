"""Print the version that a release tag must name: the one both distributions declare.

Usage: release_version.py [TAG]
"""

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROJECTS = ("pyproject.toml", "packages/xincord-plugins/pyproject.toml")


def release_version(root: Path, tag: str | None = None) -> str:
    """Return both distributions' version; fail when they differ or ``tag`` names another."""
    versions = {
        str(tomllib.loads((root / path).read_text(encoding="utf-8"))["project"]["version"])
        for path in PROJECTS
    }
    if len(versions) != 1:
        msg = f"the distributions declare different versions: {', '.join(sorted(versions))}"
        raise ValueError(msg)
    (version,) = versions
    if tag is not None and tag != f"v{version}":
        msg = f"tag {tag} does not name the distributions' version {version}"
        raise ValueError(msg)
    return version


def main(argv: list[str] | None = None) -> int:
    """Print the version, or the error and exit 1."""
    args = sys.argv[1:] if argv is None else argv
    try:
        print(release_version(ROOT, args[0] if args else None))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
