"""``/balance``: a user's own wallet, or anyone's for an administrator.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:62-71
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:141-148
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:185-188
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/MessageReplier.kt:26-42
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/en-US/message/balance.yaml:1-15
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/zh-TW/message/balance.yaml:1-15
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:29-41
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeUser, embed_dict
from plugin_fakes import golden
from xincord.plugins.economy.store import NAMESPACE, change
from xincord.plugins.economy.wallet import OPERATIONS

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
SHOWN = "The balance shows a wallet"


def balance(user: FakeMember | FakeUser, *, locale: discord.Locale = EN) -> FakeInteraction:
    """``/balance`` run by ``user`` in guild 10, with an en-US client unless ``locale``."""
    return FakeInteraction(
        {"type": 1, "name": "balance"},
        command=SimpleNamespace(name="balance"),
        user=user,
        guild=GUILD,
        locale=locale,
    )


async def show(cog: Economy, interaction: FakeInteraction, member: object = None) -> None:
    """Run the command's handler, with ``member`` as the option."""
    target = cast("discord.Member | discord.User | None", member)
    await cog.show_balance(interaction.as_interaction(), target)


def replied(interaction: FakeInteraction) -> list[dict[str, Any]]:
    """The embeds of the one edit of the deferred response."""
    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    assert fields["content"] == ""
    embeds = cast("tuple[discord.Embed, ...]", fields["embeds"])
    return [embed_dict(embed) for embed in embeds]


async def give_bob(store: Store, money: int = 1500, cost: int = 990) -> None:
    """Bob's wallet in guild 10."""
    await change(store, 10, BOB.id, OPERATIONS["set-money"], money)
    await change(store, 10, BOB.id, OPERATIONS["set-cost"], cost)


def amounts(embed: dict[str, Any]) -> list[str]:
    """The values of the embed's fields."""
    return [field["value"] for field in embed["fields"]]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=SHOWN)
@pytest.mark.parametrize("locale", [EN, ZH], ids=["en-US", "zh-TW"])
async def test_own_wallet(cog: Economy, store: Store, locale: discord.Locale) -> None:
    """Requirement: The balance shows a wallet."""
    await give_bob(store)
    interaction = balance(BOB, locale=locale)

    await show(cog, interaction)

    assert replied(interaction) == [GOLDEN["balance"][locale.value]]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=SHOWN)
async def test_no_wallet_yet(cog: Economy, store: Store) -> None:
    """Requirement: The balance shows a wallet."""
    interaction = balance(ALICE)

    await show(cog, interaction)

    [embed] = replied(interaction)
    assert embed["title"] == GOLDEN["balance"]["en-US"]["title"].replace("bob", "alice")
    assert amounts(embed) == ["0 $", "0 $"]
    assert await store.keys(NAMESPACE) == []  # v3 created the wallet and the guild's file


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=SHOWN)
@pytest.mark.parametrize("member", [BOB, FakeUser(id=7, name="bob")], ids=["member", "user"])
async def test_administrator_names_a_member(
    cog: Economy, store: Store, member: FakeMember | FakeUser
) -> None:
    """Requirement: The balance shows a wallet."""
    # A user outside the guild comes as a discord.User, as v3's asUser read anyone.
    await give_bob(store)
    interaction = balance(ADMIN)

    await show(cog, interaction, member)

    assert replied(interaction) == [GOLDEN["balance"]["en-US"]]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=SHOWN)
@pytest.mark.parametrize("locale", [EN, ZH], ids=["en-US", "zh-TW"])
async def test_member_names_someone_else(
    cog: Economy, store: Store, locale: discord.Locale
) -> None:
    """Requirement: The balance shows a wallet."""
    await give_bob(store)
    interaction = balance(ALICE, locale=locale)

    await show(cog, interaction, BOB)

    assert replied(interaction) == [GOLDEN["no-permission"][locale.value]]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=SHOWN)
async def test_member_names_themselves(cog: Economy, store: Store) -> None:
    """Requirement: The balance shows a wallet."""
    await give_bob(store)
    interaction = balance(BOB)

    await show(cog, interaction, FakeUser(id=7, name="bob"))

    assert replied(interaction) == [GOLDEN["balance"]["en-US"]]
