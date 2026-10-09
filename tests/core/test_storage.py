"""Storage: the SQLite key-value store."""

import asyncio
import json
import math
import sqlite3
from contextlib import asynccontextmanager, closing
from typing import TYPE_CHECKING, cast

import pytest

from xincord.core.storage import JSON, Store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@asynccontextmanager
async def opened(path: str | Path = ":memory:") -> AsyncGenerator[Store]:
    store = await Store.open(path)
    try:
        yield store
    finally:
        await store.close()


async def test_value_round_trips() -> None:
    """Requirement: Values are stored by namespace and key."""

    value: JSON = {"a": [1, 2.5, "x", None, True], "b": {}}

    async with opened() as store:
        await store.put("ns", "k", value)

        assert await store.get("ns", "k") == value


async def test_missing_key_and_delete() -> None:
    """Requirement: Values are stored by namespace and key."""

    async with opened() as store:
        await store.put("ns", "k", 1)

        assert await store.get("ns", "missing") is None
        assert await store.delete("ns", "k") is True
        assert await store.delete("ns", "k") is False
        assert await store.get("ns", "k") is None


async def test_namespaces_are_isolated_and_listed_in_key_order() -> None:
    """Requirement: Values are stored by namespace and key."""

    async with opened() as store:
        await store.put("one", "b", 2)
        await store.put("one", "a", 1)
        await store.put("two", "c", 3)

        assert await store.keys("one") == ["a", "b"]
        assert list((await store.items("one")).items()) == [("a", 1), ("b", 2)]
        assert await store.items("two") == {"c": 3}


@pytest.mark.parametrize("value", [{1, 2}, math.nan, {"x": math.inf}])
async def test_non_json_value_is_rejected(value: object) -> None:
    """Requirement: Only JSON values are accepted."""

    async with opened() as store:
        with pytest.raises((TypeError, ValueError)):
            await store.put("ns", "k", cast("JSON", value))

        assert await store.get("ns", "k") is None


async def test_value_survives_reopening(tmp_path: Path) -> None:
    """Requirement: Awaited writes are durable."""

    path = tmp_path / "data" / "xincord.sqlite3"

    async with opened(path) as store:
        await store.put("ns", "k", "kept")
    async with opened(path) as store:
        assert await store.get("ns", "k") == "kept"


async def test_commit_is_visible_to_another_connection(tmp_path: Path) -> None:
    """Requirement: Awaited writes are durable."""

    path = tmp_path / "xincord.sqlite3"

    async with opened(path) as store:
        await store.put("ns", "k", [1, 2])
        with closing(sqlite3.connect(path)) as other:
            row = other.execute(
                "SELECT value FROM kv WHERE namespace = ? AND key = ?",
                ("ns", "k"),
            ).fetchone()

    assert json.loads(row[0]) == [1, 2]


ATOMIC = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Read-modify-write is atomic",
)


def increment(current: JSON) -> JSON:
    return (current if isinstance(current, int) else 0) + 1


@ATOMIC
async def test_concurrent_increments() -> None:
    """Requirement: Read-modify-write is atomic."""

    async with opened() as store:
        await asyncio.gather(*(store.update("ns", "count", increment) for _ in range(100)))

        assert await store.get("ns", "count") == 100


@ATOMIC
async def test_update_returns_the_new_value() -> None:
    """Requirement: Read-modify-write is atomic."""

    async with opened() as store:
        assert await store.update("ns", "count", increment) == 1
        assert await store.update("ns", "count", increment) == 2


async def test_own_table_is_created_and_queried() -> None:
    """Requirement: Plugins can use their own tables."""

    def create(db: sqlite3.Connection) -> None:
        db.execute("CREATE TABLE example_rows (id INTEGER PRIMARY KEY, name TEXT)")
        db.executemany("INSERT INTO example_rows (name) VALUES (?)", [("a",), ("b",)])

    async with opened() as store:
        await store.run(create)
        rows = await store.run(
            lambda db: db.execute("SELECT name FROM example_rows ORDER BY id").fetchall(),
        )

    assert [row[0] for row in rows] == ["a", "b"]


async def test_failure_rolls_back() -> None:
    """Requirement: Plugins can use their own tables."""

    def write_then_fail(db: sqlite3.Connection) -> None:
        db.execute("REPLACE INTO kv (namespace, key, value) VALUES ('ns', 'k', '1')")
        msg = "boom"
        raise RuntimeError(msg)

    async with opened() as store:
        with pytest.raises(RuntimeError, match="boom"):
            await store.run(write_then_fail)

        assert await store.get("ns", "k") is None


async def test_garbage_file(tmp_path: Path) -> None:
    """Requirement: Corrupt databases are never reset."""

    path = tmp_path / "xincord.sqlite3"
    garbage = bytes(range(256)) * 16
    path.write_bytes(garbage)

    with pytest.raises(sqlite3.DatabaseError):
        await Store.open(path)

    assert path.read_bytes() == garbage


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Keyed locks serialize multi-step flows",
)
async def test_same_key_same_lock() -> None:
    """Requirement: Keyed locks serialize multi-step flows."""

    async with opened() as store:
        assert store.lock("guild:1") is store.lock("guild:1")
        assert store.lock("guild:1") is not store.lock("guild:2")
