"""v3's operations on a wallet and the boards' ranking, without Discord or storage.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/UserData.kt:11-69
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:83-138
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/JsonImpl.kt:75-120
"""

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


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Changes follow v3's arithmetic")
@pytest.mark.parametrize(("name", "expected"), CHANGED.items(), ids=list(CHANGED))
def test_each_operation(name: str, expected: Wallet) -> None:
    """Requirement: Changes follow v3's arithmetic."""
    assert OPERATIONS[name](Wallet(money=100, cost=20), 30) == expected


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Changes follow v3's arithmetic")
def test_past_32_bits() -> None:
    """Requirement: Changes follow v3's arithmetic."""
    # v3's Int wrapped 2147483647 + 1 to -2147483648, and asInt threw for values beyond 32 bits.
    assert OPERATIONS["add-money"](Wallet(money=2**31 - 1), 1) == Wallet(money=2**31)
    assert OPERATIONS["add-money"](Wallet(money=2**53), 2**53) == Wallet(money=2**54)
    assert OPERATIONS["remove-money"](Wallet(), 2**53) == Wallet(money=-(2**53), cost=2**53)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Changes follow v3's arithmetic")
def test_amounts_go_negative() -> None:
    """Requirement: Changes follow v3's arithmetic."""
    assert OPERATIONS["remove-money"](Wallet(money=10), 30) == Wallet(money=-20, cost=30)
    assert OPERATIONS["remove-cost"](Wallet(cost=10), 30) == Wallet(cost=-20)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Boards rank the wallets")
def test_order_and_ties() -> None:
    """Requirement: Boards rank the wallets."""
    wallets = {3: Wallet(money=20), 2: Wallet(money=50), 1: Wallet(money=20)}

    assert rank(wallets, "money", 25) == [(2, 50), (1, 20), (3, 20)]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Boards rank the wallets")
def test_cost_board_keeps_every_wallet() -> None:
    """Requirement: Boards rank the wallets."""
    wallets = {1: Wallet(money=5), 2: Wallet(cost=9), 3: Wallet(money=7, cost=-1)}

    assert rank(wallets, "cost", 25) == [(2, 9), (1, 0), (3, -1)]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Boards rank the wallets")
def test_limit() -> None:
    """Requirement: Boards rank the wallets."""
    wallets = {user: Wallet(money=user) for user in range(1, 31)}

    assert rank(wallets, "money", 25) == [(user, user) for user in range(30, 5, -1)]
    assert rank({}, "money", 25) == []
