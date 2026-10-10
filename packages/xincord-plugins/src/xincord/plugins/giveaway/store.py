"""Each guild's giveaways, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:49-54
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:411-415
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from xincord.core.storage import Store

    from .model import Instance

NAMESPACE = "Giveaway"  # the store namespace: the plugin's name, keys are guild IDs


class Giveaways:
    """The giveaways of every guild, one document per guild."""

    def __init__(self, store: Store) -> None:
        """Keep the shared store."""
        self.store = store

    async def get(self, guild_id: int, giveaway_id: str) -> Instance | None:
        """The guild's giveaway ``giveaway_id``, or None; nothing is written.

        Raises:
            DataError: The guild's document or the giveaway is not v3's shape.
        """
        raise NotImplementedError

    async def ids(self, guild_id: int) -> frozenset[str]:
        """The IDs of the guild's giveaways; nothing is written.

        Raises:
            DataError: The guild's document is not v3's shape.
        """
        raise NotImplementedError

    async def add(self, instance: Instance) -> None:
        """Store a new giveaway in its guild's document.

        Raises:
            DataError: The guild already has a giveaway with its ID, or its document is not v3's
                shape; nothing is written.
        """
        raise NotImplementedError

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
        raise NotImplementedError
