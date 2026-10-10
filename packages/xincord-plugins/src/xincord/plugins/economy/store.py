"""Each guild's wallets, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/JsonImpl.kt:17-173
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/json/JsonData.kt:3-10
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xincord.core.storage import Store

    from .wallet import Operation, Wallet

NAMESPACE = "Economy"  # the store namespace: the plugin's name, keys are guild IDs


class DataError(Exception):
    """A stored wallet is not v3's shape; it is left as it is, and the message says where."""


async def read(store: Store, guild_id: int, user_id: int) -> Wallet:
    """Stub."""
    raise NotImplementedError


async def read_all(store: Store, guild_id: int) -> dict[int, Wallet]:
    """Stub."""
    raise NotImplementedError


async def change(
    store: Store, guild_id: int, user_id: int, operation: Operation, value: int
) -> tuple[Wallet, Wallet]:
    """Stub."""
    raise NotImplementedError
