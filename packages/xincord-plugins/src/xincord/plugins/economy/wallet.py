"""Wallets, the operations on them and the boards' ranking, without Discord or storage."""

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

type Kind = Literal["money", "cost"]  # what a board ranks
type Operation = Callable[[Wallet, int], Wallet]


@dataclass(frozen=True)
class Wallet:
    """A user's money (the balance) and cost (the spending) in one guild, 0 and 0 at first.

    Python's integers are exact and never wrap; either amount may be negative.
    """

    money: int = 0
    cost: int = 0


def add_money(wallet: Wallet, value: int) -> Wallet:
    """Add ``value`` to the money ."""
    return replace(wallet, money=wallet.money + value)


def remove_money(wallet: Wallet, value: int) -> Wallet:
    """Move ``value`` from the money to the cost: a purchase."""
    return Wallet(money=wallet.money - value, cost=wallet.cost + value)


def set_money(wallet: Wallet, value: int) -> Wallet:
    """Set the money to ``value`` ."""
    return replace(wallet, money=value)


def add_cost(wallet: Wallet, value: int) -> Wallet:
    """Add ``value`` to the cost ."""
    return replace(wallet, cost=wallet.cost + value)


def remove_cost(wallet: Wallet, value: int) -> Wallet:
    """Subtract ``value`` from the cost ."""
    return replace(wallet, cost=wallet.cost - value)


def set_cost(wallet: Wallet, value: int) -> Wallet:
    """Set the cost to ``value`` ."""
    return replace(wallet, cost=value)


# The change commands, in their order, and what each does to the member's wallet.
OPERATIONS: Mapping[str, Operation] = {
    "add-money": add_money,
    "remove-money": remove_money,
    "set-money": set_money,
    "add-cost": add_cost,
    "remove-cost": remove_cost,
    "set-cost": set_cost,
}


def rank(wallets: Mapping[int, Wallet], kind: Kind, limit: int) -> list[tuple[int, int]]:
    """Return the first ``limit`` user IDs and amounts, from the highest money or cost.

    Every wallet counts, those at 0 too. Equal amounts are ordered by user ID, the lowest first.
    """
    amounts = [
        (user_id, wallet.money if kind == "money" else wallet.cost)
        for user_id, wallet in wallets.items()
    ]
    return sorted(amounts, key=lambda pair: (-pair[1], pair[0]))[:limit]
