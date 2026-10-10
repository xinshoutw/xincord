"""Each guild's listen channel settings, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/JsonManager.kt:17-117
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/json/JsonData.kt:5-15
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Literal

from .settings import Setting

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable, Container, Iterable

    from xincord.core.storage import JSON, Store

NAMESPACE = "VoiceLogger"  # the plugin's name; keys are guild IDs
CHANNEL_ID = re.compile(r"[1-9][0-9]*")  # the keys of a document: listen channel IDs in decimal

type Kind = Literal["allow", "block"]
type Entries = dict[int, tuple[JSON, Setting]]  # each stored entry with the settings it holds


class DataError(Exception):
    """A stored document is not of v3's shape; it is left as it is."""


async def read_settings(store: Store, guild_id: int) -> dict[int, Setting]:
    """Return the guild's settings by listen channel ID, in stored order, and write nothing.

    Raises:
        DataError: The document or one of its entries is not v3's.
    """
    return {channel: setting for channel, (_, setting) in (await _read(store, guild_id)).items()}


async def read_setting(store: Store, guild_id: int, channel_id: int) -> Setting:
    """Return the settings of listen channel ``channel_id``, and write nothing.

    A channel without an entry is in the allow mode with empty lists: v3's ``computeIfAbsent``
    default, which v3 kept in memory only.

    Raises:
        DataError: The document or one of its entries is not v3's.
    """
    found = (await _read(store, guild_id)).get(channel_id)
    return Setting() if found is None else found[1]


async def toggle(store: Store, guild_id: int, channel_id: int) -> Setting:
    """Switch the listen channel between the allow and the block mode; return its settings.

    Raises:
        DataError: The document or one of its entries is not v3's; nothing is written.
    """
    return await _change(
        store,
        guild_id,
        channel_id,
        lambda setting: replace(setting, allow_mode=not setting.allow_mode),
    )


async def add_channels(
    store: Store, guild_id: int, channel_id: int, kind: Kind, ids: Iterable[int]
) -> Setting:
    """Add ``ids`` after the listen channel's ``kind`` list; return its settings.

    IDs that are listed already are skipped. A new entry starts in the allow mode, as the menu
    showed it: v3 saved it with ``allow_mode`` false.

    Raises:
        DataError: The document or one of its entries is not v3's; nothing is written.
    """
    added = tuple(ids)

    def add(setting: Setting) -> Setting:
        listed = setting.allow if kind == "allow" else setting.block
        return replace(setting, **{kind: tuple(dict.fromkeys((*listed, *added)))})

    return await _change(store, guild_id, channel_id, add)


async def remove(store: Store, guild_id: int, channel_id: int) -> bool:
    """Delete the listen channel's settings; return whether it had some.

    The other listen channels keep theirs (v3 deleted the guild's whole file), and the document
    goes with its last entry.

    Raises:
        DataError: The document or one of its entries is not v3's; nothing is written.
    """
    async with _lock(store, guild_id):
        entries = await _read(store, guild_id)
        if channel_id not in entries:
            return False
        kept: dict[str, JSON] = {
            str(channel): raw for channel, (raw, _) in entries.items() if channel != channel_id
        }
        if kept:
            await store.put(NAMESPACE, str(guild_id), kept)
        else:
            await store.delete(NAMESPACE, str(guild_id))
        return True


async def forget(store: Store, guild_id: int) -> None:
    """Delete the guild's settings."""
    async with _lock(store, guild_id):
        await store.delete(NAMESPACE, str(guild_id))


async def guild_ids(store: Store) -> list[int]:
    """Return the guilds with settings, in order."""
    return sorted(int(key) for key in await store.keys(NAMESPACE))


async def prune(store: Store, guild_id: int, known: Container[int]) -> list[int]:
    """Drop from every list the IDs that ``known`` lacks; return them, each once, in order.

    v3 filtered the lists to the guild's channels when it loaded them. Nothing is written when
    nothing is dropped; a changed entry is written in v3's shape, and the others stay as they were.

    Raises:
        DataError: The document or one of its entries is not v3's; nothing is written.
    """
    async with _lock(store, guild_id):
        entries = await _read(store, guild_id)
        dropped: dict[int, None] = {}
        document: dict[str, JSON] = {}
        for channel, (raw, setting) in entries.items():
            listed = (*setting.allow, *setting.block)
            dropped |= dict.fromkeys(item for item in listed if item not in known)
            kept = replace(
                setting,
                allow=tuple(item for item in setting.allow if item in known),
                block=tuple(item for item in setting.block if item in known),
            )
            document[str(channel)] = raw if kept == setting else _entry(kept)
        if dropped:
            await store.put(NAMESPACE, str(guild_id), document)
        return list(dropped)


async def _change(
    store: Store, guild_id: int, channel_id: int, change: Callable[[Setting], Setting]
) -> Setting:
    """Apply ``change`` to the listen channel's settings and store them if they changed.

    The changed entry is written in v3's shape, in place or after the others; the other entries
    stay as they were.
    """
    async with _lock(store, guild_id):
        entries = await _read(store, guild_id)
        found = entries.get(channel_id)
        old = Setting() if found is None else found[1]
        new = change(old)
        if new != old:
            document: dict[str, JSON] = {str(channel): raw for channel, (raw, _) in entries.items()}
            document[str(channel_id)] = _entry(new)
            await store.put(NAMESPACE, str(guild_id), document)
        return new


def _lock(store: Store, guild_id: int) -> asyncio.Lock:
    """The lock of the guild's document: every change reads and writes it under it.

    discord.py runs handlers concurrently; v3 kept its settings in one shared map.
    """
    return store.lock(f"{NAMESPACE}:{guild_id}")


async def _read(store: Store, guild_id: int) -> Entries:
    """The guild's stored entries by listen channel ID, each with its settings."""
    document = await store.get(NAMESPACE, str(guild_id))
    if document is None:
        return {}
    if not isinstance(document, dict):
        msg = f"guild {guild_id}: the settings are not a JSON object: {document!r}"
        raise DataError(msg)
    entries: Entries = {}
    for key, entry in document.items():
        if not CHANNEL_ID.fullmatch(key):
            msg = f"guild {guild_id}: {key!r} is not a channel ID"
            raise DataError(msg)
        entries[int(key)] = (entry, _setting(entry, guild_id, key))
    return entries


def _setting(entry: JSON, guild_id: int, key: str) -> Setting:
    """The settings of v3's entry; other fields are ignored, as Moshi ignored them.

    Moshi required ``allow_mode``, ``allow`` and ``block``, and Core then replaced the guild's whole
    file with an empty object.
    """
    fields = entry if isinstance(entry, dict) else {}
    mode = fields.get("allow_mode")
    allow, block = _ids(fields.get("allow")), _ids(fields.get("block"))
    if not isinstance(mode, bool) or allow is None or block is None:
        msg = f"guild {guild_id}: the settings of channel {key} are not v3's: {entry!r}"
        raise DataError(msg)
    return Setting(allow_mode=mode, allow=allow, block=block)


def _ids(value: JSON) -> tuple[int, ...] | None:
    """The IDs of a stored list, each once in order (v3's sets), or None if it is not one."""
    if not isinstance(value, list):
        return None
    ids = [item for item in value if type(item) is int]  # booleans are not IDs
    return tuple(dict.fromkeys(ids)) if len(ids) == len(value) else None


def _entry(setting: Setting) -> dict[str, JSON]:
    """v3's entry for ``setting``, in Moshi's field order, which a migration can copy as it is."""
    return {
        "allow_mode": setting.allow_mode,
        "allow": [*setting.allow],
        "block": [*setting.block],
    }
