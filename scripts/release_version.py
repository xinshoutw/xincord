"""Print the version that a release tag must name: the one both distributions declare.

xincord-plugins requires xincord at exactly that version: both are released together.

Usage: release_version.py [TAG]
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROJECTS = ("pyproject.toml", "packages/xincord-plugins/pyproject.toml")
CORE = re.compile(r"xincord(?![\w.-])")  # a requirement on the core, not on xincord-plugins


def release_version(root: Path, tag: str | None = None) -> str:
    """Return both distributions' version.

    Fail when the versions differ, the plugins do not require the core at that version, or
    ``tag`` names another.
    """
    core, plugins = (
        tomllib.loads((root / path).read_text(encoding="utf-8"))["project"] for path in PROJECTS
    )
    versions = {str(core["version"]), str(plugins["version"])}
    if len(versions) != 1:
        msg = f"the distributions declare different versions: {', '.join(sorted(versions))}"
        raise ValueError(msg)
    (version,) = versions
    requires = [
        "".join(str(item).split())
        for item in plugins.get("dependencies", [])
        if CORE.match(str(item))
    ]
    if requires != [f"xincord=={version}"]:
        found = ", ".join(requires) or "nothing"
        msg = f"xincord-plugins must require xincord=={version}, not {found}"
        raise ValueError(msg)
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
