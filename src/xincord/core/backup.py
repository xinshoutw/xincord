"""An online backup of the working directory's ``data/``: ``python -m xincord.core.backup``."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from pathlib import Path

KEEP = 7  # backups kept, the newest


def backup(data: Path, backups: Path, keep: int = KEEP, now: datetime | None = None) -> Path:
    """Copy ``data`` into a new directory of ``backups``, keep the newest ``keep``; return it."""
    raise NotImplementedError


def main(argv: Sequence[str] | None = None) -> int:
    """Back up ``data/`` as the command line asks and return the exit status."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
