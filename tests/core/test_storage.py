"""Storage: the SQLite key-value store."""

import json
import math
import sqlite3
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

import pytest

from xincord.core.storage import JSON, Store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


def xfail(requirement: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=requirement)


STORED = xfail("Values are stored by namespace and key")
JSON_ONLY = xfail("Only JSON values are accepted")
DURABLE = xfail("Awaited writes are durable")


@asynccontextmanager
async def opened(path: str | Path = ":memory:") -> AsyncGenerator[Store]:
    store = await Store.open(path)
    try:
        yield store
    finally:
        await store.close()


@STORED
async def test_value_round_trips() -> None:
    value: JSON = {"a": [1, 2.5, "x", None, True], "b": {}}

    async with opened() as store:
        await store.put("ns", "k", value)

        assert await store.get("ns", "k") == value


@STORED
async def test_missing_key_and_delete() -> None:
    async with opened() as store:
        await store.put("ns", "k", 1)

        assert await store.get("ns", "missing") is None
        assert await store.delete("ns", "k") is True
        assert await store.delete("ns", "k") is False
        assert await store.get("ns", "k") is None


@STORED
async def test_namespaces_are_isolated_and_listed_in_key_order() -> None:
    async with opened() as store:
        await store.put("one", "b", 2)
        await store.put("one", "a", 1)
        await store.put("two", "c", 3)

        assert await store.keys("one") == ["a", "b"]
        assert list((await store.items("one")).items()) == [("a", 1), ("b", 2)]
        assert await store.items("two") == {"c": 3}


@JSON_ONLY
@pytest.mark.parametrize("value", [{1, 2}, math.nan, {"x": math.inf}])
async def test_non_json_value_is_rejected(value: object) -> None:
    async with opened() as store:
        with pytest.raises((TypeError, ValueError)):
            await store.put("ns", "k", cast("JSON", value))

        assert await store.get("ns", "k") is None


@DURABLE
async def test_value_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "data" / "xincord.sqlite3"

    async with opened(path) as store:
        await store.put("ns", "k", "kept")
    async with opened(path) as store:
        assert await store.get("ns", "k") == "kept"


@DURABLE
async def test_commit_is_visible_to_another_connection(tmp_path: Path) -> None:
    path = tmp_path / "xincord.sqlite3"

    async with opened(path) as store:
        await store.put("ns", "k", [1, 2])
        with sqlite3.connect(path) as other:
            row = other.execute(
                "SELECT value FROM kv WHERE namespace = ? AND key = ?",
                ("ns", "k"),
            ).fetchone()

    assert json.loads(row[0]) == [1, 2]
