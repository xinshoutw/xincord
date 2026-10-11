"""An online backup of the working directory's ``data/``: ``python -m xincord.core.backup``.

The bot keeps running: each SQLite database is copied through SQLite's backup API, its last
committed state, and every other file as it is. A backup is a directory of ``backups/`` named after
the UTC time it was taken; the newest ``--keep`` stay.
"""

import argparse
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

DATA = Path("data")
BACKUPS = Path("backups")
KEEP = 7  # backups kept, the newest
NAME = re.compile(r"\d{8}T\d{6}Z")  # a backup's directory: the UTC time it was taken
HEADER = b"SQLite format 3" + bytes(1)  # the first 16 bytes of every SQLite database
SIDECARS = ("-journal", "-wal", "-shm")  # SQLite's files beside a database; a copy needs none


def backup(data: Path, backups: Path, keep: int = KEEP, now: datetime | None = None) -> Path:
    """Copy ``data`` into a new directory of ``backups``, keep the newest ``keep``; return it.

    The files go into a hidden partial directory, renamed once complete and removed on an error.
    """
    taken = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    target = backups / taken
    if target.exists():
        msg = f"{target} exists: one backup per second"
        raise FileExistsError(msg)
    partial = backups / f".{taken}.partial"
    partial.mkdir(parents=True)
    try:
        for source in data.rglob("*"):
            if source.is_file() and not source.name.endswith(SIDECARS):
                _copy(source, partial / source.relative_to(data))
        partial.rename(target)
    except BaseException:
        shutil.rmtree(partial)
        raise
    kept = sorted(path for path in backups.iterdir() if path.is_dir() and NAME.fullmatch(path.name))
    for old in kept[:-keep]:
        shutil.rmtree(old)
    return target


def _copy(source: Path, copy: Path) -> None:
    """Copy one file: a database through SQLite's backup API, anything else as it is."""
    copy.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as file:
        database = file.read(len(HEADER)) == HEADER
    if not database:
        shutil.copy2(source, copy)
        return
    # One step under a read lock, retried while the bot holds a write lock: the committed state.
    with closing(sqlite3.connect(source)) as db, closing(sqlite3.connect(copy)) as out:
        db.backup(out)


def main(argv: Sequence[str] | None = None) -> int:
    """Back up ``data/`` as the command line asks and return the exit status."""
    parser = argparse.ArgumentParser(
        prog="python -m xincord.core.backup", description="Back up data/ while the bot runs."
    )
    parser.add_argument(
        "destination", nargs="?", type=Path, default=BACKUPS, help="default: backups"
    )
    parser.add_argument("--keep", type=int, default=KEEP, help=f"backups kept (default: {KEEP})")
    args = parser.parse_args(argv)
    if args.keep < 1:
        parser.error("--keep takes 1 or more")
    if not DATA.is_dir():
        parser.error("no data/ here: run it in the bot's directory")
    target = backup(DATA, args.destination, args.keep)
    files = [path for path in target.rglob("*") if path.is_file()]
    size = sum(path.stat().st_size for path in files) // 1024
    print(f"{target}: {len(files)} files, {size} KiB")  # noqa: T201 - command-line output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
