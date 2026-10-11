"""Each guild's giveaways, kept in the shared store as v3's documents."""

import logging
from typing import TYPE_CHECKING

from .model import DataError, drawn, instance_json, is_due, parse_instance

if TYPE_CHECKING:
    import asyncio
    import random
    from collections.abc import Callable

    from xincord.core.storage import JSON, Store

    from .model import Instance

logger = logging.getLogger(__name__)

NAMESPACE = "Giveaway"  # the store namespace: the plugin's name, keys are guild IDs


class Giveaways:
    """The giveaways of every guild, one document per guild.

    Every change of a guild's document runs under the guild's lock and rewrites one entry, keeping
    the others as they are; only this plugin writes its namespace, so joins, draws and new
    giveaways never lose one another. v3 changed its in-memory files from three threads without
    locks.
    """

    def __init__(self, store: Store) -> None:
        """Keep the shared store."""
        self.store = store
        self.reported: set[str] = set()  # the broken entries that the automatic draw logged

    async def guild_ids(self) -> list[str]:
        """The keys of the guilds' documents, which are guild IDs unless someone edited them."""
        return await self.store.keys(NAMESPACE)

    async def draw_due(self, guild_id: int, now: int, rng: random.Random) -> list[Instance]:
        """Draw the guild's due giveaways at ``now`` and store them; return them.

        One write for the guild, under its lock, before anything is posted: v3 saved after
        queuing the posts, and a draw and the automatic draw could both draw. A broken document
        or entry is skipped, and logged the first time.
        """
        async with self.lock(guild_id):
            try:
                document = await self._document(guild_id)
            except DataError as error:
                self._report(f"guild {guild_id}", error)
                return []
            due: dict[str, Instance] = {}
            for key, entry in document.items():
                try:
                    instance = parse_instance(entry, _where(guild_id, key))
                except DataError as error:
                    self._report(_where(guild_id, key), error)
                    continue
                if is_due(instance, now):
                    due[key] = drawn(instance, now, rng)
            if due:
                written = {key: instance_json(instance) for key, instance in due.items()}
                updated: dict[str, JSON] = {**document, **written}
                await self.store.put(NAMESPACE, str(guild_id), updated)
            return list(due.values())

    def _report(self, where: str, error: DataError) -> None:
        """Log a broken document or entry the first time the automatic draw skips it."""
        if where not in self.reported:
            self.reported.add(where)
            logger.warning("Giveaway skips %s in the automatic draw: %s", where, error)

    def lock(self, guild_id: int) -> asyncio.Lock:
        """The lock of the guild's document, the same across reloads."""
        return self.store.lock(f"{NAMESPACE}:{guild_id}")

    async def get(self, guild_id: int, giveaway_id: str) -> Instance | None:
        """The guild's giveaway ``giveaway_id``, or None; nothing is written.

        Raises:
            DataError: The guild's document or the giveaway is not v3's shape.
        """
        document = await self._document(guild_id)
        if giveaway_id not in document:
            return None
        return parse_instance(document[giveaway_id], _where(guild_id, giveaway_id))

    async def ids(self, guild_id: int) -> frozenset[str]:
        """The IDs of the guild's giveaways; nothing is written.

        Raises:
            DataError: The guild's document is not v3's shape.
        """
        return frozenset(await self._document(guild_id))

    async def add(self, instance: Instance) -> None:
        """Store a new giveaway in its guild's document.

        Raises:
            DataError: The guild already has a giveaway with its ID, or its document is not v3's
                shape; nothing is written.
        """
        async with self.lock(instance.guild_id):
            document = await self._document(instance.guild_id)
            if instance.id in document:
                msg = f"{_where(instance.guild_id, instance.id)}: the ID is taken"
                raise DataError(msg)
            updated: dict[str, JSON] = {**document, instance.id: instance_json(instance)}
            await self.store.put(NAMESPACE, str(instance.guild_id), updated)

    async def change[T](
        self,
        guild_id: int,
        giveaway_id: str,
        transition: Callable[[Instance], tuple[T, Instance]],
    ) -> tuple[T, Instance] | None:
        """Run ``transition`` on the stored giveaway and store what it returns, if it changed.

        Returns None, writing nothing, when the guild has no such giveaway.

        Raises:
            DataError: The guild's document or the giveaway is not v3's shape; nothing is written.
        """
        async with self.lock(guild_id):
            document = await self._document(guild_id)
            if giveaway_id not in document:
                return None
            before = parse_instance(document[giveaway_id], _where(guild_id, giveaway_id))
            result, after = transition(before)
            if after != before:
                updated: dict[str, JSON] = {**document, giveaway_id: instance_json(after)}
                await self.store.put(NAMESPACE, str(guild_id), updated)
            return result, after

    async def _document(self, guild_id: int) -> dict[str, JSON]:
        """The guild's document, empty when it has none.

        Raises:
            DataError: It is not a JSON object.
        """
        document = await self.store.get(NAMESPACE, str(guild_id))
        if document is None:
            return {}
        if not isinstance(document, dict):
            msg = f"guild {guild_id}: the giveaways are not a JSON object: {document!r}"
            raise DataError(msg)
        return document


def _where(guild_id: int, giveaway_id: str) -> str:
    """Names a stored giveaway in errors."""
    return f"guild {guild_id}, giveaway {giveaway_id}"
