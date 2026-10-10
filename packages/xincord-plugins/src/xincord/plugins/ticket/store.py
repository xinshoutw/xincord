"""Each guild's panels, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:62-67
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:839-852
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:219-232
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable

    from xincord.core.storage import Store

    from .model import Entry

NAMESPACE = "Ticket"  # the store namespace: the plugin's name, keys are guild IDs

type Place = Callable[[int], Awaitable[object]]  # puts the button of an index on its message


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
        raise NotImplementedError

    async def add(
        self, guild_id: int, message_id: str, entry: Entry, place: Place | None = None
    ) -> int:
        """Append ``entry`` to the panel's list under the guild's lock and return its index.

        ``place``, when given, puts the button on its message first, with the index; when it
        raises, nothing is stored. The document's other values are written back as they were.

        Raises:
            DataError: The guild's document or the panel's list is not v3's shape.
        """
        raise NotImplementedError

    async def forget(self, guild_id: int) -> None:
        """Delete the guild's panels, as v3 deleted its file."""
        raise NotImplementedError

    async def guild_ids(self) -> list[str]:
        """The keys of the guilds' documents, which are guild IDs unless someone edited them."""
        raise NotImplementedError
