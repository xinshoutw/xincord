"""Each guild's panels, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:62-67
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:839-852
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:219-232
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

import re
from typing import TYPE_CHECKING

from .model import DataError, entry_json, parse_entry

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable

    from xincord.core.storage import JSON, Store

    from .model import Entry

NAMESPACE = "Ticket"  # the store namespace: the plugin's name, keys are guild IDs
# A button's index as v3 read it with Kotlin's toIntOrNull: an Int, ASCII digits only here.
INDEX = re.compile(r"[+-]?[0-9]{1,9}")

type Undo = Callable[[], Awaitable[object]]  # takes a placed button off its message again
type Place = Callable[[int], Awaitable[Undo]]  # puts the button of an index on its message


class Panels:
    """The panels of every guild, one document per guild: ``{"<message ID>": [entry, ...]}``.

    A button's index in its message is its entry's position in the message's list. Every change
    runs under the guild's lock; reads write nothing (v3 created the guild's file when reading).
    """

    def __init__(self, store: Store) -> None:
        """Keep the shared store."""
        self.store = store

    def lock(self, guild_id: int) -> asyncio.Lock:
        """The lock of the guild's document, the same across reloads."""
        return self.store.lock(f"{NAMESPACE}:{guild_id}")

    async def entry(self, guild_id: int, message_id: str, index: str) -> Entry | None:
        """The entry of button ``index`` (decimal text) of the panel ``message_id``, or None.

        Raises:
            DataError: The guild's document or the entry is not v3's shape.
        """
        entries = (await self._document(guild_id)).get(message_id)
        if entries is None or not INDEX.fullmatch(index):
            return None
        listed = _entries(entries, guild_id, message_id)
        position = int(index)
        if not 0 <= position < len(listed):
            return None
        return parse_entry(listed[position], _where(guild_id, message_id))

    async def add(
        self, guild_id: int, message_id: str, entry: Entry, place: Place | None = None
    ) -> int:
        """Append ``entry`` to the panel's list under the guild's lock and return its index.

        ``place``, when given, puts the button on its message first, with the index, and gives
        back what takes it off again: when ``place`` raises, nothing is stored, and when the store
        fails, the button is taken off before the error goes on, so that no button stays without
        its entry. The document's other values are written back as they were.

        Raises:
            DataError: The guild's document or the panel's list is not v3's shape.
            sqlite3.Error: The store failed.
        """
        async with self.lock(guild_id):
            document = await self._document(guild_id)
            entries = _entries(document.get(message_id, []), guild_id, message_id)
            index = len(entries)
            undo = None if place is None else await place(index)
            listed: list[JSON] = [*entries, entry_json(entry)]
            updated: dict[str, JSON] = {**document, message_id: listed}
            try:
                await self.store.put(NAMESPACE, str(guild_id), updated)
            except Exception:
                if undo is not None:
                    await undo()
                raise
            return index

    async def forget(self, guild_id: int) -> None:
        """Delete the guild's panels, as v3 deleted its file."""
        async with self.lock(guild_id):
            await self.store.delete(NAMESPACE, str(guild_id))

    async def guild_ids(self) -> list[str]:
        """The keys of the guilds' documents, which are guild IDs unless someone edited them."""
        return await self.store.keys(NAMESPACE)

    async def _document(self, guild_id: int) -> dict[str, JSON]:
        """The guild's document, empty when it has none.

        Raises:
            DataError: It is not a JSON object.
        """
        document = await self.store.get(NAMESPACE, str(guild_id))
        if document is None:
            return {}
        if not isinstance(document, dict):
            msg = f"guild {guild_id}: the panels are not a JSON object: {document!r}"
            raise DataError(msg)
        return document


def _entries(value: JSON, guild_id: int, message_id: str) -> list[JSON]:
    """A panel's stored list of entries.

    Raises:
        DataError: It is not a JSON array.
    """
    if not isinstance(value, list):
        msg = f"{_where(guild_id, message_id)}: the entries are not a JSON array: {value!r}"
        raise DataError(msg)
    return value


def _where(guild_id: int, message_id: str) -> str:
    """Names a stored panel in errors."""
    return f"guild {guild_id}, message {message_id}"
