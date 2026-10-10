"""The six change commands, their permission check and v3's ``Bad Value``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:42-53
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:73-179
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:190-198
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/MessageReplier.kt:26-42
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/en-US/message/no-permission.yaml:1-9
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/zh-TW/message/no-permission.yaml:1-9
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeUser, embed_dict
from plugin_fakes import golden
from xincord.plugins.economy.store import NAMESPACE, change, read
from xincord.plugins.economy.wallet import OPERATIONS, Wallet

if TYPE_CHECKING:
    from xincord.core.storage import Store
    from xincord.plugins.economy.cog import Economy

GOLDEN = golden("economy")
EN = discord.Locale.american_english
ZH = discord.Locale.taiwan_chinese
GUILD = FakeGuild(id=10)
ADMIN = FakeMember(GUILD, id=1, name="admin")  # listed in the conftest's admin_id
BOB = FakeMember(GUILD, id=7, name="bob")
ALICE = FakeMember(GUILD, id=2, name="alice")  # not listed
# Bob's wallet, with the money 100 and the cost 20, after each command with the value 30.
AFTER = {
    "add-money": Wallet(money=130, cost=20),
    "remove-money": Wallet(money=70, cost=50),
    "set-money": Wallet(money=30, cost=20),
    "add-cost": Wallet(money=100, cost=50),
    "remove-cost": Wallet(money=100, cost=-10),
    "set-cost": Wallet(money=100, cost=30),
}
ADMINS_ONLY = "Only administrators change wallets and see boards"


def run(name: str, user: FakeMember, *, locale: discord.Locale = EN) -> FakeInteraction:
    """The command ``name`` run by ``user`` in guild 10, with an en-US client unless ``locale``."""
    return FakeInteraction(
        {"type": 1, "name": name},
        command=SimpleNamespace(name=name),
        user=user,
        guild=GUILD,
        locale=locale,
    )


async def change_by(
    cog: Economy, interaction: FakeInteraction, member: FakeMember | FakeUser, value: int
) -> None:
    """Run the change commands' handler with the options ``member`` and ``value``."""
    target = cast("discord.Member | discord.User", member)
    await cog.change_wallet(interaction.as_interaction(), target, value)


def replied(interaction: FakeInteraction) -> list[dict[str, Any]]:
    """The embeds of the one edit of the deferred response."""
    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    assert fields["content"] == ""
    embeds = cast("tuple[discord.Embed, ...]", fields["embeds"])
    return [embed_dict(embed) for embed in embeds]


def numbers(embed: dict[str, Any]) -> list[list[str]]:
    """The amounts that each field of ``embed`` shows."""
    return [
        [part for part in field["value"].split() if part.lstrip("-").isdigit()]
        for field in embed["fields"]
    ]


async def give_bob(store: Store) -> None:
    """Bob's wallet in guild 10: the money 100 and the cost 20."""
    await change(store, 10, BOB.id, OPERATIONS["set-money"], 100)
    await change(store, 10, BOB.id, OPERATIONS["set-cost"], 20)


@pytest.mark.parametrize("locale", [EN, ZH], ids=["en-US", "zh-TW"])
@pytest.mark.parametrize("name", list(AFTER))
async def test_change_reply(cog: Economy, store: Store, name: str, locale: discord.Locale) -> None:
    """Requirement: Administrators change wallets."""
    await give_bob(store)
    interaction = run(name, ADMIN, locale=locale)

    await change_by(cog, interaction, BOB, 30)

    assert replied(interaction) == [GOLDEN["changes"][name][locale.value]]
    assert await read(store, 10, BOB.id) == AFTER[name]


async def test_user_outside_the_guild(cog: Economy, store: Store) -> None:
    """Requirement: Administrators change wallets."""
    carol = FakeUser(id=8, name="carol")  # Discord resolved no member: a discord.User
    interaction = run("add-money", ADMIN)

    await change_by(cog, interaction, carol, 5)

    [embed] = replied(interaction)
    assert embed["title"] == GOLDEN["balance"]["en-US"]["title"].replace("bob", "carol")
    assert numbers(embed) == [["0", "5"], ["0"]]
    assert await read(store, 10, carol.id) == Wallet(money=5)


async def test_amounts_past_32_bits(cog: Economy, store: Store) -> None:
    """Requirement: Administrators change wallets."""
    await change_by(cog, run("add-money", ADMIN), BOB, 2**53)
    interaction = run("add-money", ADMIN)

    await change_by(cog, interaction, BOB, 2**53)

    [embed] = replied(interaction)
    assert numbers(embed) == [[str(2**53), str(2**54)], ["0"]]
    assert await read(store, 10, BOB.id) == Wallet(money=2**54)


@pytest.mark.parametrize("locale", [EN, ZH], ids=["en-US", "zh-TW"])
@pytest.mark.parametrize("name", list(AFTER))
async def test_member_changes_a_wallet(
    cog: Economy, store: Store, name: str, locale: discord.Locale
) -> None:
    """Requirement: Only administrators change wallets and see boards."""
    interaction = run(name, ALICE, locale=locale)
    interaction.permissions = discord.Permissions(administrator=True)  # Discord's, not admin_id

    await change_by(cog, interaction, BOB, -5)  # refused before the value is checked

    assert replied(interaction) == [GOLDEN["no-permission"][locale.value]]
    assert await store.keys(NAMESPACE) == []


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=ADMINS_ONLY)
@pytest.mark.parametrize("name", ["top-money", "top-cost"])
async def test_member_asks_for_a_board(cog: Economy, store: Store, name: str) -> None:
    """Requirement: Only administrators change wallets and see boards."""
    await give_bob(store)
    interaction = run(name, ALICE)

    await cog.show_board(interaction.as_interaction())

    assert replied(interaction) == [GOLDEN["no-permission"]["en-US"]]


@pytest.mark.parametrize("name", list(AFTER))
async def test_negative_amount(cog: Economy, store: Store, name: str) -> None:
    """Requirement: Negative amounts are refused."""
    await give_bob(store)
    interaction = run(name, ADMIN, locale=ZH)

    await change_by(cog, interaction, BOB, -1)

    # v3's text, the same in every locale, as plain content.
    assert interaction.sent == [("edit_original_response", {"content": "Bad Value"})]
    assert await read(store, 10, BOB.id) == Wallet(money=100, cost=20)


async def test_zero(cog: Economy, store: Store) -> None:
    """Requirement: Negative amounts are refused."""
    interaction = run("add-money", ADMIN)

    await change_by(cog, interaction, BOB, 0)

    [embed] = replied(interaction)
    assert embed["author"] == GOLDEN["changes"]["add-money"]["en-US"]["author"]
    assert numbers(embed) == [["0", "0"], ["0"]]
    assert await store.get(NAMESPACE, "10") == {"7": {"cost": 0, "money": 0}}


async def test_change_outside_a_guild(cog: Economy) -> None:
    """Requirement: The commands are localized guild commands."""
    interaction = run("add-money", ADMIN)
    interaction.guild = None

    await change_by(cog, interaction, BOB, 5)

    assert interaction.sent == []


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The commands are localized guild commands"
)
async def test_board_outside_a_guild(cog: Economy) -> None:
    """Requirement: The commands are localized guild commands."""
    interaction = run("top-money", ADMIN)
    interaction.guild = None

    await cog.show_board(interaction.as_interaction())

    assert interaction.sent == []
