"""Persistent storage: JSON values by namespace and key, in one SQLite database."""

import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Callable

type JSON = bool | int | float | str | list[JSON] | dict[str, JSON] | None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
) WITHOUT ROWID
"""


class Store:
    """An async key-value store of JSON values, backed by one SQLite connection.

    Every operation runs on one worker thread, one transaction per call, so awaited writes are
    committed and operations never interleave.
    """

    def __init__(self, connection: sqlite3.Connection, executor: ThreadPoolExecutor) -> None:
        """Wrap an open connection; use :meth:`open` instead."""
        self._connection = connection
        self._executor = executor

    @classmethod
    async def open(cls, path: str | Path) -> Self:
        """Open the database at ``path`` (``":memory:"`` for a temporary one).

        Raises:
            sqlite3.DatabaseError: The file exists but is not a usable database. It is left
                unchanged.
        """
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xincord-storage")

        def connect() -> sqlite3.Connection:
            if str(path) != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, autocommit=False)
            try:
                connection.execute(_SCHEMA)
                connection.commit()
            except sqlite3.Error:
                connection.close()
                raise
            return connection

        try:
            connection = await asyncio.get_running_loop().run_in_executor(executor, connect)
        except BaseException:
            executor.shutdown()
            raise
        return cls(connection, executor)

    async def close(self) -> None:
        """Close the connection; the store cannot be used afterwards."""
        await asyncio.get_running_loop().run_in_executor(self._executor, self._connection.close)
        self._executor.shutdown()

    async def run[T](self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run ``fn`` with the connection on the database thread, as one transaction.

        The transaction is committed when ``fn`` returns and rolled back when it raises. Plugins
        use this for their own tables, named ``<plugin>_<table>``.
        """

        def transaction() -> T:
            try:
                result = fn(self._connection)
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()
            return result

        return await asyncio.get_running_loop().run_in_executor(self._executor, transaction)

    async def get(self, namespace: str, key: str) -> JSON:
        """Return the value stored under ``namespace`` and ``key``, or None if there is none."""
        row = await self.run(
            lambda db: db.execute(
                "SELECT value FROM kv WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone(),
        )
        return None if row is None else json.loads(row[0])

    async def put(self, namespace: str, key: str, value: JSON) -> None:
        """Store ``value``, replacing any previous value.

        Raises:
            TypeError: ``value`` contains something JSON cannot represent.
            ValueError: ``value`` contains NaN or an infinity.
        """
        text = json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
        await self.run(
            lambda db: db.execute(
                "REPLACE INTO kv (namespace, key, value) VALUES (?, ?, ?)",
                (namespace, key, text),
            ),
        )

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a key and report whether it existed."""
        cursor = await self.run(
            lambda db: db.execute(
                "DELETE FROM kv WHERE namespace = ? AND key = ?",
                (namespace, key),
            ),
        )
        return cursor.rowcount > 0

    async def keys(self, namespace: str) -> list[str]:
        """Return the keys of ``namespace`` in order."""
        rows = await self.run(
            lambda db: db.execute(
                "SELECT key FROM kv WHERE namespace = ? ORDER BY key",
                (namespace,),
            ).fetchall(),
        )
        return [row[0] for row in rows]

    async def items(self, namespace: str) -> dict[str, JSON]:
        """Return the keys and values of ``namespace``, ordered by key."""
        rows = await self.run(
            lambda db: db.execute(
                "SELECT key, value FROM kv WHERE namespace = ? ORDER BY key",
                (namespace,),
            ).fetchall(),
        )
        return {row[0]: json.loads(row[1]) for row in rows}
