"""Wallets, v3's operations on them and the boards' ranking, without Discord or storage.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/UserData.kt:11-69
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/JsonImpl.kt:75-120
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

type Kind = Literal["money", "cost"]  # what a board ranks
type Operation = Callable[[Wallet, int], Wallet]


@dataclass(frozen=True)
class Wallet:
    """A user's money (the balance) and cost (the spending) in one guild, 0 and 0 at first."""

    money: int = 0
    cost: int = 0


def add_money(wallet: Wallet, value: int) -> Wallet:
    """Stub."""
    raise NotImplementedError


def remove_money(wallet: Wallet, value: int) -> Wallet:
    """Stub."""
    raise NotImplementedError


def set_money(wallet: Wallet, value: int) -> Wallet:
    """Stub."""
    raise NotImplementedError


def add_cost(wallet: Wallet, value: int) -> Wallet:
    """Stub."""
    raise NotImplementedError


def remove_cost(wallet: Wallet, value: int) -> Wallet:
    """Stub."""
    raise NotImplementedError


def set_cost(wallet: Wallet, value: int) -> Wallet:
    """Stub."""
    raise NotImplementedError


# v3's change commands, in v3's order, and what each does to the member's wallet.
OPERATIONS: Mapping[str, Operation] = {
    "add-money": add_money,
    "remove-money": remove_money,
    "set-money": set_money,
    "add-cost": add_cost,
    "remove-cost": remove_cost,
    "set-cost": set_cost,
}


def rank(wallets: Mapping[int, Wallet], kind: Kind, limit: int) -> list[tuple[int, int]]:
    """Stub."""
    raise NotImplementedError
