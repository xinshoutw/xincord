"""Persistent storage: JSON values by namespace and key, in one SQLite database."""

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable
    from pathlib import Path

type JSON = bool | int | float | str | list[JSON] | dict[str, JSON] | None


class Store:
    """An async key-value store of JSON values, backed by one SQLite connection."""

    @classmethod
    async def open(cls, path: str | Path) -> Self:
        """Open the database at ``path`` (``":memory:"`` for a temporary one)."""
        raise NotImplementedError

    async def close(self) -> None:
        """Close the connection; the store cannot be used afterwards."""
        raise NotImplementedError

    async def get(self, namespace: str, key: str) -> JSON:
        """Return the value stored under ``namespace`` and ``key``, or None if there is none."""
        raise NotImplementedError

    async def put(self, namespace: str, key: str, value: JSON) -> None:
        """Store ``value``, replacing any previous value."""
        raise NotImplementedError

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a key and report whether it existed."""
        raise NotImplementedError

    async def keys(self, namespace: str) -> list[str]:
        """Return the keys of ``namespace`` in order."""
        raise NotImplementedError

    async def items(self, namespace: str) -> dict[str, JSON]:
        """Return the keys and values of ``namespace``, ordered by key."""
        raise NotImplementedError

    async def run[T](self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run ``fn`` with the connection on the database thread, as one transaction."""
        raise NotImplementedError
