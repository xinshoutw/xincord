"""Requirements: Online backup, Backup retention, Backup command."""

import re
import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xincord.core.backup import backup, main

TAKEN = datetime(2026, 10, 12, 4, 30, tzinfo=UTC)
NAME = "20261012T043000Z"  # the backup taken at TAKEN


def database(path: Path, *rows: str) -> sqlite3.Connection:
    """Create a database at ``path`` holding ``rows``, committed; return its open connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, autocommit=False)
    db.execute("CREATE TABLE kv (value TEXT)")
    db.executemany("INSERT INTO kv VALUES (?)", [(row,) for row in rows])
    db.commit()
    return db


def values(path: Path) -> list[str]:
    """Return the rows of the database at ``path``."""
    with closing(sqlite3.connect(path)) as db:
        return [row[0] for row in db.execute("SELECT value FROM kv ORDER BY value")]


def test_consistent_copy_while_the_bot_writes(tmp_path: Path) -> None:
    """Requirement: Online backup, scenario A consistent copy while the bot writes."""
    data = tmp_path / "data"
    bot = database(data / "xincord.db", "committed")
    bot.execute("INSERT INTO kv VALUES ('uncommitted')")  # the bot's open transaction
    database(data / "ChatLogger" / "messages-20240829T023137Z.db", "message").close()
    (data / "Plugin").mkdir()
    (data / "Plugin" / "notes.txt").write_bytes(b"kept as it is")
    assert (data / "xincord.db-journal").exists()  # the open transaction's rollback journal

    try:
        target = backup(data, tmp_path / "backups", now=TAKEN)
    finally:
        bot.rollback()
        bot.close()

    assert target == tmp_path / "backups" / NAME
    assert values(target / "xincord.db") == ["committed"]
    assert values(target / "ChatLogger" / "messages-20240829T023137Z.db") == ["message"]
    assert (target / "Plugin" / "notes.txt").read_bytes() == b"kept as it is"
    assert not list(target.rglob("*-journal"))
    assert [path.name for path in (tmp_path / "backups").iterdir()] == [NAME]


def test_failed_backup_leaves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Online backup, scenario A failed backup."""
    data = tmp_path / "data"
    (data / "Plugin").mkdir(parents=True)
    (data / "Plugin" / "notes.txt").write_text("x", encoding="utf-8")

    def full(*_args: object, **_kwargs: object) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(shutil, "copy2", full)

    with pytest.raises(OSError, match="disk full"):
        backup(data, tmp_path / "backups", now=TAKEN)
    assert list((tmp_path / "backups").iterdir()) == []


def test_two_backups_in_one_second(tmp_path: Path) -> None:
    """Requirement: Online backup, scenario Two backups in one second."""
    data = tmp_path / "data"
    database(data / "xincord.db", "first").close()
    first = backup(data, tmp_path / "backups", now=TAKEN)
    database(data / "ChatLogger" / "messages-20240829T023137Z.db", "later").close()

    with pytest.raises(FileExistsError, match=NAME):
        backup(data, tmp_path / "backups", now=TAKEN)
    assert sorted(path.name for path in first.rglob("*")) == ["xincord.db"]
    assert [path.name for path in (tmp_path / "backups").iterdir()] == [NAME]


def test_the_oldest_backups_go(tmp_path: Path) -> None:
    """Requirement: Backup retention, scenario The oldest go."""
    data = tmp_path / "data"
    data.mkdir()
    backups = tmp_path / "backups"
    taken = [f"202610{day:02}T043000Z" for day in range(1, 9)]  # 8 backups, October 1 to 8
    for name in taken:
        (backups / name).mkdir(parents=True)
    (backups / "notes.txt").write_text("the operator's", encoding="utf-8")

    backup(data, backups, now=TAKEN)

    remaining = sorted(path.name for path in backups.iterdir())
    assert remaining == sorted([*taken[2:], NAME, "notes.txt"])


def test_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Requirement: Backup command, scenario Output and errors."""
    monkeypatch.chdir(tmp_path)
    database(Path("data/xincord.db"), "row").close()
    Path("data/notes.txt").write_text("x", encoding="utf-8")

    assert main([]) == 0
    (target,) = Path("backups").iterdir()
    assert re.fullmatch(rf"{re.escape(str(target))}: 2 files, \d+ KiB\n", capsys.readouterr().out)

    with pytest.raises(SystemExit) as no_keep:
        main(["--keep", "0"])
    shutil.rmtree("data")
    with pytest.raises(SystemExit) as no_data:
        main([])
    assert (no_keep.value.code, no_data.value.code) == (2, 2)
