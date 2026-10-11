"""Each guild's bindings and rooms, kept in the shared store."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Collection, Iterable

    from xincord.core.storage import JSON, Store

NAMESPACE = "DynamicVoiceChannel"  # the bindings: the plugin's name, keys are guild IDs
# The rooms the plugin created, by guild ID; v3 kept them in MongoDB's
# DynamicVoiceChannel.generated_cache.
ROOMS = f"{NAMESPACE}.rooms"
ROOM_ID = re.compile(r"[1-9][0-9]*")  # the keys of a rooms document: channel IDs in decimal

type Key = tuple[int, str]  # a binding's category ID and lobby name, v3's DataContainer identity


class DataError(Exception):
    """A stored document is not of the expected shape; it is left as it is."""


@dataclass(frozen=True)
class Binding:
    """v3's ``DataContainer``: a lobby, by its category and exact name, and the room format.

    v3's second format, which v3 stored and never used, is gone (``dvc-one-name-format``).
    """

    category_id: int
    default_name: str
    format_name_1: str = ""

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


async def read_rooms(store: Store, guild_id: int) -> dict[int, int]:
    """Return the guild's rooms, each with the member it was created for, and write nothing.

    Raises:
        DataError: The document is not an object of room IDs to member IDs.
    """
    return _rooms(await store.get(ROOMS, str(guild_id)), guild_id)


async def track(store: Store, guild_id: int, room_id: int, owner_id: int) -> None:
    """Record ``room_id`` as a room of the guild, created for ``owner_id``.

    v3 kept the owner too, as the value of the room's MongoDB document, and never read it.

    Raises:
        DataError: The document is not an object of room IDs to member IDs; nothing is written.
    """
    async with _lock(store, guild_id):
        rooms = await read_rooms(store, guild_id)
        await store.put(ROOMS, str(guild_id), _rooms_document(rooms | {room_id: owner_id}))


async def untrack(store: Store, guild_id: int, room_id: int) -> None:
    """Forget ``room_id``; nothing is written when it is not a room of the guild.

    The document goes with the guild's last room.

    Raises:
        DataError: The document is not an object of room IDs to member IDs; nothing is written.
    """
    async with _lock(store, guild_id):
        rooms = await read_rooms(store, guild_id)
        if room_id not in rooms:
            return
        left = {room: owner for room, owner in rooms.items() if room != room_id}
        if left:
            await store.put(ROOMS, str(guild_id), _rooms_document(left))
        else:
            await store.delete(ROOMS, str(guild_id))


async def forget(store: Store, guild_id: int) -> None:
    """Delete the guild's bindings and rooms.

    v3 deleted the guild's binding file only, and left its rooms in MongoDB.
    """
    async with _lock(store, guild_id):
        await store.delete(NAMESPACE, str(guild_id))
        await store.delete(ROOMS, str(guild_id))


async def guild_ids(store: Store) -> list[int]:
    """Return the guilds with bindings or rooms, in order."""
    keys = {*await store.keys(NAMESPACE), *await store.keys(ROOMS)}
    return sorted(int(key) for key in keys)


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

    ``formatName2`` is one of them now, whatever its value. Moshi refused an entry without
    ``categoryId`` or ``defaultName``, or with a null format, and Core then replaced the guild's
    whole file with an empty list.
    """
    fields = entry if isinstance(entry, dict) else {}
    category_id, name = fields.get("categoryId"), fields.get("defaultName")
    format_1 = fields.get("formatName1", "")
    if (
        type(category_id) is not int  # booleans and fractions are not IDs
        or not isinstance(name, str)
        or not isinstance(format_1, str)
    ):
        msg = f"guild {guild_id}: a binding is not v3's: {entry!r}"
        raise DataError(msg)
    return Binding(category_id, name, format_1)


def _entry(binding: Binding) -> dict[str, JSON]:
    """v3's entry for ``binding``, in Moshi's field order, which a migration can copy as it is."""
    return {
        "categoryId": binding.category_id,
        "defaultName": binding.default_name,
        "formatName1": binding.format_name_1,
    }


def _rooms(document: JSON, guild_id: int) -> dict[int, int]:
    """The rooms of a stored document: decimal room IDs, each with an integer member ID."""
    if document is None:
        return {}
    entries = document.items() if isinstance(document, dict) else ()
    rooms = {
        int(room): owner
        for room, owner in entries
        if ROOM_ID.fullmatch(room) and type(owner) is int  # booleans are not IDs
    }
    if not isinstance(document, dict) or len(rooms) < len(document):
        msg = f"guild {guild_id}: the rooms are not room IDs with member IDs: {document!r}"
        raise DataError(msg)
    return rooms


def _rooms_document(rooms: dict[int, int]) -> dict[str, JSON]:
    """The stored document of ``rooms``."""
    return {str(room): owner for room, owner in rooms.items()}
