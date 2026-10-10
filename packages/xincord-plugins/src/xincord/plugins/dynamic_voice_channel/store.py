"""Each guild's bindings and rooms, kept in the shared store.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/JsonManager.kt:30-142
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/json/JsonData.kt:3-29
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Collection, Iterable

    from xincord.core.storage import JSON, Store

NAMESPACE = "DynamicVoiceChannel"  # the bindings: the plugin's name, keys are guild IDs

type Key = tuple[int, str]  # a binding's category ID and lobby name, v3's DataContainer identity


class DataError(Exception):
    """A stored document is not of the expected shape; it is left as it is."""


@dataclass(frozen=True)
class Binding:
    """v3's ``DataContainer``: a lobby, by its category and exact name, and the room formats."""

    category_id: int
    default_name: str
    format_name_1: str = ""
    format_name_2: str = ""  # stored and never used, as in v3

    @property
    def key(self) -> Key:
        """The category and the lobby name, which identify a binding."""
        return (self.category_id, self.default_name)


async def read_bindings(store: Store, guild_id: int) -> list[Binding]:
    """Return the guild's bindings in the stored order, and write nothing.

    A guild without a document has none; a missing format reads as empty, as Moshi's defaults.

    Raises:
        DataError: The document or one of its entries is not v3's.
    """
    return [binding for _, binding in await _read(store, guild_id)]


def find(bindings: Iterable[Binding], category_id: int, name: str) -> Binding | None:
    """Return the first binding of ``category_id`` whose lobby name is exactly ``name``.

    v3 compared names exactly, case included, and kept the first of duplicate entries when it
    loaded a guild's file.
    """
    return next((binding for binding in bindings if binding.key == (category_id, name)), None)


async def bind(store: Store, guild_id: int, binding: Binding) -> None:
    """Store ``binding`` in place of those with the same category and lobby name.

    The new entry goes after the guild's other entries, which stay as they are. v3 appended a
    duplicate instead, which won until the next restart and lost afterwards.

    Raises:
        DataError: The document or one of its entries is not v3's; nothing is written.
    """
    async with _lock(store, guild_id):
        entries = await _read(store, guild_id)
        kept = [entry for entry, found in entries if found.key != binding.key]
        await store.put(NAMESPACE, str(guild_id), [*kept, _entry(binding)])


async def unbind(store: Store, guild_id: int, category_id: int, name: str) -> bool:
    """Remove the bindings of ``category_id`` and ``name``; return whether there was one.

    Raises:
        DataError: The document or one of its entries is not v3's; nothing is written.
    """
    return await _remove(store, guild_id, {(category_id, name)}) > 0


async def drop(store: Store, guild_id: int, keys: Collection[Key]) -> None:
    """Remove the bindings whose category and lobby name are in ``keys``.

    Raises:
        DataError: The document or one of its entries is not v3's; nothing is written.
    """
    await _remove(store, guild_id, keys)


async def _remove(store: Store, guild_id: int, keys: Collection[Key]) -> int:
    """Remove the entries of ``keys`` and return how many there were.

    Nothing is written when there is none, and the document goes with its last entry.
    """
    async with _lock(store, guild_id):
        entries = await _read(store, guild_id)
        kept = [entry for entry, found in entries if found.key not in keys]
        if len(kept) < len(entries):
            if kept:
                await store.put(NAMESPACE, str(guild_id), kept)
            else:
                await store.delete(NAMESPACE, str(guild_id))
        return len(entries) - len(kept)


def _lock(store: Store, guild_id: int) -> asyncio.Lock:
    """The lock of the guild's documents: every change reads and writes them under it.

    discord.py runs handlers concurrently; v3 synchronized on its in-memory objects.
    """
    return store.lock(f"{NAMESPACE}:{guild_id}")


async def _read(store: Store, guild_id: int) -> list[tuple[JSON, Binding]]:
    """The guild's stored entries, each with the binding it holds."""
    document = await store.get(NAMESPACE, str(guild_id))
    if document is None:
        return []
    if not isinstance(document, list):
        msg = f"guild {guild_id}: the bindings are not a JSON list: {document!r}"
        raise DataError(msg)
    return [(entry, _binding(entry, guild_id)) for entry in document]


def _binding(entry: JSON, guild_id: int) -> Binding:
    """The binding of v3's entry; other fields are ignored, as Moshi ignored them.

    Moshi refused an entry without ``categoryId`` or ``defaultName``, or with a null format, and
    Core then replaced the guild's whole file with an empty list.
    """
    fields = entry if isinstance(entry, dict) else {}
    category_id, name = fields.get("categoryId"), fields.get("defaultName")
    format_1, format_2 = fields.get("formatName1", ""), fields.get("formatName2", "")
    if (
        type(category_id) is not int  # booleans and fractions are not IDs
        or not isinstance(name, str)
        or not isinstance(format_1, str)
        or not isinstance(format_2, str)
    ):
        msg = f"guild {guild_id}: a binding is not v3's: {entry!r}"
        raise DataError(msg)
    return Binding(category_id, name, format_1, format_2)


def _entry(binding: Binding) -> dict[str, JSON]:
    """v3's entry for ``binding``, in Moshi's field order, which a migration can copy as it is."""
    return {
        "categoryId": binding.category_id,
        "defaultName": binding.default_name,
        "formatName1": binding.format_name_1,
        "formatName2": binding.format_name_2,
    }
