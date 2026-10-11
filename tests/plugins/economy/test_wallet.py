"""The operations on a wallet and the boards' ranking, without Discord or storage."""

import pytest

from xincord.plugins.economy.wallet import OPERATIONS, Wallet, rank

# A wallet with the money 100 and the cost 20 after each command with the value 30.
CHANGED = {
    "add-money": Wallet(money=130, cost=20),
    "remove-money": Wallet(money=70, cost=50),
    "set-money": Wallet(money=30, cost=20),
    "add-cost": Wallet(money=100, cost=50),
    "remove-cost": Wallet(money=100, cost=-10),
    "set-cost": Wallet(money=100, cost=30),
}


@pytest.mark.parametrize(("name", "expected"), CHANGED.items(), ids=list(CHANGED))
def test_each_operation(name: str, expected: Wallet) -> None:
    """Requirement: Changes are exact integer arithmetic."""
    assert OPERATIONS[name](Wallet(money=100, cost=20), 30) == expected


def test_past_32_bits() -> None:
    """Requirement: Changes are exact integer arithmetic."""
    # Past 32 bits, the amounts stay exact.
    assert OPERATIONS["add-money"](Wallet(money=2**31 - 1), 1) == Wallet(money=2**31)
    assert OPERATIONS["add-money"](Wallet(money=2**53), 2**53) == Wallet(money=2**54)
    assert OPERATIONS["remove-money"](Wallet(), 2**53) == Wallet(money=-(2**53), cost=2**53)


def test_amounts_go_negative() -> None:
    """Requirement: Changes are exact integer arithmetic."""
    assert OPERATIONS["remove-money"](Wallet(money=10), 30) == Wallet(money=-20, cost=30)
    assert OPERATIONS["remove-cost"](Wallet(cost=10), 30) == Wallet(cost=-20)


def test_order_and_ties() -> None:
    """Requirement: Boards rank the wallets."""
    wallets = {3: Wallet(money=20), 2: Wallet(money=50), 1: Wallet(money=20)}

    assert rank(wallets, "money", 25) == [(2, 50), (1, 20), (3, 20)]


def test_cost_board_keeps_every_wallet() -> None:
    """Requirement: Boards rank the wallets."""
    wallets = {1: Wallet(money=5), 2: Wallet(cost=9), 3: Wallet(money=7, cost=-1)}

    assert rank(wallets, "cost", 25) == [(2, 9), (1, 0), (3, -1)]


def test_limit() -> None:
    """Requirement: Boards rank the wallets."""
    wallets = {user: Wallet(money=user) for user in range(1, 31)}

    assert rank(wallets, "money", 25) == [(user, user) for user in range(30, 5, -1)]
    assert rank({}, "money", 25) == []
