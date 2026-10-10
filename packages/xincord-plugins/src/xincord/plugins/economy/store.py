"""Each guild's wallets, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/JsonImpl.kt:17-173
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/json/JsonData.kt:3-10
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

import re
from typing import TYPE_CHECKING

from .wallet import Wallet

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.storage import JSON, Store

    from .wallet import Operation

NAMESPACE = "Economy"  # the store namespace: the plugin's name, keys are guild IDs
# The keys of the users' entries: their IDs in decimal, as v3 wrote them. v3 skipped other keys.
USER_ID = re.compile(r"[1-9][0-9]*")


class DataError(Exception):
    """A stored wallet is not v3's shape; it is left as it is, and the message says where."""


async def read(store: Store, guild_id: int, user_id: int) -> Wallet:
    """Return the user's wallet in the guild, 0 and 0 without an entry, and write nothing.

    v3 created the entry, and the guild's file, when it read a wallet.

    Raises:
        DataError: The guild's document or the user's entry is not v3's shape.
    """
    entries = _entries(await store.get(NAMESPACE, str(guild_id)), guild_id)
    return _wallet(entries, guild_id, user_id)


async def read_all(store: Store, guild_id: int) -> dict[int, Wallet]:
    """Return the guild's wallets by user ID, and write nothing.

    Raises:
        DataError: The guild's document or a user's entry is not v3's shape.
    """
    entries = _entries(await store.get(NAMESPACE, str(guild_id)), guild_id)
    return {
        int(key): _wallet(entries, guild_id, int(key)) for key in entries if USER_ID.fullmatch(key)
    }


async def change(
    store: Store, guild_id: int, user_id: int, operation: Operation, value: int
) -> tuple[Wallet, Wallet]:
    """Apply ``operation`` with ``value`` to the user's wallet; return it before and after.

    Reading and writing the guild's document is one store transaction, so concurrent changes never
    lose one another: discord.py runs handlers concurrently, and v3 had no lock between its
    threads. Only the user's entry is rewritten, with v3's two fields; the others stay as they are.

    Raises:
        DataError: The guild's document or the user's entry is not v3's shape; nothing is written.
    """
    changed: list[tuple[Wallet, Wallet]] = []

    def apply(document: JSON) -> JSON:
        entries = _entries(document, guild_id)
        before = _wallet(entries, guild_id, user_id)
        after = operation(before, value)
        changed.append((before, after))
        updated: dict[str, JSON] = {**entries, str(user_id): _entry(after)}
        return updated

    await store.update(NAMESPACE, str(guild_id), apply)
    return changed[0]


def _entries(document: JSON, guild_id: int) -> dict[str, JSON]:
    """The guild's entries by key; a guild without a document has none."""
    if document is None:
        return {}
    if not isinstance(document, dict):
        msg = f"guild {guild_id}: the wallets are not a JSON object: {document!r}"
        raise DataError(msg)
    return document


def _wallet(entries: Mapping[str, JSON], guild_id: int, user_id: int) -> Wallet:
    """The user's wallet from v3's entry ``{"cost": <int>, "money": <int>}``, 0 and 0 without one.

    Other fields are ignored, as Moshi ignored them. Anything else raises, where v3's Moshi failed
    too and Core then replaced the guild's whole file with an empty one.
    """
    key = str(user_id)
    if key not in entries:
        return Wallet()
    entry = entries[key]
    fields = entry if isinstance(entry, dict) else {}
    money, cost = fields.get("money"), fields.get("cost")
    if type(money) is not int or type(cost) is not int:  # booleans are not amounts
        msg = f"guild {guild_id}: the wallet of user {user_id} is not v3's: {entry!r}"
        raise DataError(msg)
    return Wallet(money=money, cost=cost)


def _entry(wallet: Wallet) -> dict[str, JSON]:
    """v3's entry for ``wallet``, in Moshi's field order, which a migration can copy as it is."""
    return {"cost": wallet.cost, "money": wallet.money}
