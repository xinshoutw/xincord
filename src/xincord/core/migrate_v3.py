"""Migrate a v3 (XsDiscordBotKt) core ``config.yaml`` to the xincord schema.

Run ``python -m xincord.core.migrate_v3 <server directory>`` once per installation.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def migrate_core_config(v3: Mapping[str, object]) -> tuple[dict[str, object], list[str]]:
    """Convert a parsed v3 core config to the new schema.

    Args:
        v3: The parsed v3 ``config.yaml``.

    Returns:
        The new config mapping and one report line per entry that could not be converted.
    """
    raise NotImplementedError


def migrate_directory(root: Path) -> list[str]:
    """Migrate ``root/config.yaml`` in place, keeping the original as ``config.v3.yaml``.

    Args:
        root: The server directory of a v3 installation.

    Returns:
        Report lines describing what was done or why nothing was changed.
    """
    raise NotImplementedError


def main(argv: Sequence[str] | None = None) -> int:
    """Migrate the directory named on the command line (default: the current directory)."""
    args = sys.argv[1:] if argv is None else argv
    for line in migrate_directory(Path(args[0] if args else ".")):
        print(line)  # noqa: T201 - command-line output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
