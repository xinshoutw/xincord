"""The stored messages: one row per message in the plugin's table of the shared store.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:16-188
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xincord.core.storage import Store

BATCH = 1000  # the messages that one transaction of the retention deletes at most


@dataclass(frozen=True)
class Stored:
    """A stored message: its latest text, its author, and how often its text changed."""

    text: str
    user_id: int
    count: int


@dataclass(frozen=True)
class Edit:
    """A stored message's new text: the text before, the author, and the changes with this one."""

    before: str
    user_id: int
    count: int


class MessageLog:
    """The plugin's table of stored messages, ``ChatLogger_messages``, in the shared store."""

    def __init__(self, store: Store) -> None:
        """Keep the store whose database holds the table."""
        self.store = store

    async def create(self) -> None:
        """Create the table and its index, unless they exist."""
        raise NotImplementedError

    async def add(
        self, message_id: int, guild_id: int, channel_id: int, user_id: int, text: str
    ) -> None:
        """Store a new message with no change counted."""
        raise NotImplementedError

    async def edit(self, message_id: int, text: str) -> Edit | None:
        """Store a message's new text and count the change."""
        raise NotImplementedError

    async def pop(self, message_id: int) -> Stored | None:
        """Take a deleted message out of the store."""
        raise NotImplementedError

    async def pop_all(self, message_ids: Iterable[int]) -> list[tuple[int, Stored]]:
        """Take the deleted messages of a bulk deletion out of the store."""
        raise NotImplementedError

    async def prune(self, before: int, batch: int = BATCH) -> int:
        """Delete the messages whose IDs are below ``before``."""
        raise NotImplementedError

    async def forget(self, guild_id: int) -> int:
        """Delete a guild's messages."""
        raise NotImplementedError

    async def guild_ids(self) -> list[int]:
        """Return the guilds with stored messages."""
        raise NotImplementedError
