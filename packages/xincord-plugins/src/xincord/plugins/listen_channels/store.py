"""Each guild's listen channel settings, kept in the shared store."""

import logging
import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from .settings import Setting

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable, Container, Iterable

    from xincord.core.storage import JSON, Store

logger = logging.getLogger(__name__)

ID = re.compile(r"[1-9][0-9]*")  # a guild or channel ID in decimal, as the keys hold them

type Kind = Literal["allow", "block"]
type Entries = dict[int, tuple[JSON, Setting]]  # each stored entry with the settings it holds


class DataError(Exception):
    """A stored document is not of the settings' shape; it is left as it is."""


@dataclass(frozen=True)
class ListenSettings:
    """One plugin's listen channel settings in ``store``, under the plugin's name.

    Each guild has one document, under ``namespace`` and the guild's ID, holding the entries by
    listen channel ID. Every change reads and writes the document under the guild's lock.
    """

    store: Store
    namespace: str  # the plugin's name: VoiceLogger or ChatLogger

    async def read_settings(self, guild_id: int) -> dict[int, Setting]:
        """Return the guild's settings by listen channel ID, in stored order, and write nothing.

        Raises:
            DataError: The document or one of its entries is not valid.
        """
        return {channel: setting for channel, (_, setting) in (await self._read(guild_id)).items()}

    async def read_setting(self, guild_id: int, channel_id: int) -> Setting:
        """Return the settings of listen channel ``channel_id``, and write nothing.

        A channel without an entry is in the allow mode with empty lists, which
        is not written.

        Raises:
            DataError: The document or one of its entries is not valid.
        """
        found = (await self._read(guild_id)).get(channel_id)
        return Setting() if found is None else found[1]

    async def toggle(self, guild_id: int, channel_id: int) -> Setting:
        """Switch the listen channel between the allow and the block mode; return its settings.

        Raises:
            DataError: The document or one of its entries is not valid; nothing is written.
        """
        return await self._change(
            guild_id,
            channel_id,
            lambda setting: replace(setting, allow_mode=not setting.allow_mode),
        )

    async def add_channels(
        self, guild_id: int, channel_id: int, kind: Kind, ids: Iterable[int]
    ) -> Setting:
        """Add ``ids`` after the listen channel's ``kind`` list; return its settings.

        IDs that are listed already are skipped. A new entry starts in the allow mode, as the menu
        shows it.

        Raises:
            DataError: The document or one of its entries is not valid; nothing is written.
        """
        added = tuple(ids)

        def add(setting: Setting) -> Setting:
            listed = setting.allow if kind == "allow" else setting.block
            return replace(setting, **{kind: tuple(dict.fromkeys((*listed, *added)))})

        return await self._change(guild_id, channel_id, add)

    async def remove(self, guild_id: int, channel_id: int) -> bool:
        """Delete the listen channel's settings; return whether it had some.

        The other listen channels keep theirs, and the document
        goes with its last entry.

        Raises:
            DataError: The document or one of its entries is not valid; nothing is written.
        """
        async with self._lock(guild_id):
            entries = await self._read(guild_id)
            if channel_id not in entries:
                return False
            kept: dict[str, JSON] = {
                str(channel): raw for channel, (raw, _) in entries.items() if channel != channel_id
            }
            if kept:
                await self.store.put(self.namespace, str(guild_id), kept)
            else:
                await self.store.delete(self.namespace, str(guild_id))
            return True

    async def forget(self, guild_id: int) -> None:
        """Delete the guild's settings."""
        async with self._lock(guild_id):
            await self.store.delete(self.namespace, str(guild_id))

    async def guild_ids(self) -> list[int]:
        """Return the guilds with settings, in order.

        A key that is not a guild ID (a hand edit or a faulty migration; the plugins never write
        one) is left as it is, with a warning.
        """
        ids: list[int] = []
        for key in await self.store.keys(self.namespace):
            if ID.fullmatch(key):
                ids.append(int(key))
            else:
                logger.warning(
                    "%s ignores the settings stored under %r, which is not a guild ID",
                    self.namespace,
                    key,
                )
        return sorted(ids)

    async def prune(self, guild_id: int, gone: Container[int]) -> list[int]:
        """Drop the IDs of ``gone`` from every list; return the ones dropped, each once, in order.

        Nothing is written when nothing is dropped; a changed entry is written in the settings'
        shape, and the others stay as they were.

        Raises:
            DataError: The document or one of its entries is not valid; nothing is written.
        """
        async with self._lock(guild_id):
            entries = await self._read(guild_id)
            dropped: dict[int, None] = {}
            document: dict[str, JSON] = {}
            for channel, (raw, setting) in entries.items():
                listed = (*setting.allow, *setting.block)
                dropped |= dict.fromkeys(item for item in listed if item in gone)
                kept = replace(
                    setting,
                    allow=tuple(item for item in setting.allow if item not in gone),
                    block=tuple(item for item in setting.block if item not in gone),
                )
                document[str(channel)] = raw if kept == setting else _entry(kept)
            if dropped:
                await self.store.put(self.namespace, str(guild_id), document)
            return list(dropped)

    async def _change(
        self, guild_id: int, channel_id: int, change: Callable[[Setting], Setting]
    ) -> Setting:
        """Apply ``change`` to the listen channel's settings and store them if they changed.

        The changed entry is written in the settings' shape, in place or after the others; the other
        entries stay as they were.
        """
        async with self._lock(guild_id):
            entries = await self._read(guild_id)
            found = entries.get(channel_id)
            old = Setting() if found is None else found[1]
            new = change(old)
            if new != old:
                document: dict[str, JSON] = {
                    str(channel): raw for channel, (raw, _) in entries.items()
                }
                document[str(channel_id)] = _entry(new)
                await self.store.put(self.namespace, str(guild_id), document)
            return new

    def _lock(self, guild_id: int) -> asyncio.Lock:
        """The lock of the guild's document: every change reads and writes it under it.

        discord.py runs handlers concurrently.
        """
        return self.store.lock(f"{self.namespace}:{guild_id}")

    async def _read(self, guild_id: int) -> Entries:
        """The guild's stored entries by listen channel ID, each with its settings."""
        document = await self.store.get(self.namespace, str(guild_id))
        if document is None:
            return {}
        if not isinstance(document, dict):
            msg = f"guild {guild_id}: the settings are not a JSON object: {document!r}"
            raise DataError(msg)
        entries: Entries = {}
        for key, entry in document.items():
            if not ID.fullmatch(key):
                msg = f"guild {guild_id}: {key!r} is not a channel ID"
                raise DataError(msg)
            entries[int(key)] = (entry, _setting(entry, guild_id, key))
        return entries


def _setting(entry: JSON, guild_id: int, key: str) -> Setting:
    """An entry's ``allow_mode``, ``allow`` and ``block``; other fields are ignored."""
    fields = entry if isinstance(entry, dict) else {}
    mode = fields.get("allow_mode")
    allow, block = _ids(fields.get("allow")), _ids(fields.get("block"))
    if not isinstance(mode, bool) or allow is None or block is None:
        msg = f"guild {guild_id}: the settings of channel {key} are not valid: {entry!r}"
        raise DataError(msg)
    return Setting(allow_mode=mode, allow=allow, block=block)


def _ids(value: JSON) -> tuple[int, ...] | None:
    """The IDs of a stored list, each once in order, or None if it is not one."""
    if not isinstance(value, list):
        return None
    ids = [item for item in value if type(item) is int]  # booleans are not IDs
    return tuple(dict.fromkeys(ids)) if len(ids) == len(value) else None


def _entry(setting: Setting) -> dict[str, JSON]:
    """The entry for ``setting``."""
    return {
        "allow_mode": setting.allow_mode,
        "allow": [*setting.allow],
        "block": [*setting.block],
    }
