"""v3's ``economy@`` buttons: any button with an Economy ID shows the presser's wallet.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Event.kt:127-131
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:34-39
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:55-60
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/info.yaml:9
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/GlobalUtil.kt:58-59
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, embed_dict
from plugin_fakes import golden
from xincord.plugins.economy.cog import IDS
from xincord.plugins.economy.store import NAMESPACE, change
from xincord.plugins.economy.wallet import OPERATIONS

if TYPE_CHECKING:
    from xincord.core.storage import Store
    from xincord.plugins.economy.cog import Economy

GOLDEN = golden("economy")
EN = discord.Locale.american_english
ZH = discord.Locale.taiwan_chinese
GUILD = FakeGuild(id=10)
BOB = FakeMember(GUILD, id=7, name="bob")  # not an administrator: buttons are for everyone
NEW_ID = "economy:1:a=balance"


def press(
    custom_id: str = NEW_ID, *, locale: discord.Locale = EN, component_type: int = 2
) -> FakeInteraction:
    """Bob presses the component ``custom_id`` in guild 10."""
    return FakeInteraction(
        {"component_type": component_type, "custom_id": custom_id},
        type=discord.InteractionType.component,
        user=BOB,
        guild=GUILD,
        locale=locale,
    )


def shown(interaction: FakeInteraction) -> list[dict[str, Any]]:
    """The embeds of the ephemeral response: deferred, then edited, as v3's deferReply(true)."""
    deferred, (method, fields) = interaction.sent[:2]
    assert deferred == ("response.defer", {"ephemeral": True, "thinking": True})
    assert method == "edit_original_response"
    embeds = cast("tuple[discord.Embed, ...]", fields["embeds"])
    return [embed_dict(embed) for embed in embeds]


async def give_bob(store: Store) -> None:
    """Bob's wallet in guild 10: the money 1500 and the cost 990."""
    await change(store, 10, BOB.id, OPERATIONS["set-money"], 1500)
    await change(store, 10, BOB.id, OPERATIONS["set-cost"], 990)


@pytest.mark.parametrize("locale", [EN, ZH], ids=["en-US", "zh-TW"])
@pytest.mark.parametrize("custom_id", [NEW_ID, "economy:1:", "economy@"])
async def test_button(cog: Economy, store: Store, custom_id: str, locale: discord.Locale) -> None:
    """Requirement: Economy buttons show the presser's wallet."""
    await give_bob(store)
    interaction = press(custom_id, locale=locale)

    await cog.handle(interaction.as_interaction(), IDS.parse(custom_id))

    assert shown(interaction) == [GOLDEN["balance"][locale.value]]


async def test_no_wallet_yet(cog: Economy, store: Store) -> None:
    """Requirement: Economy buttons show the presser's wallet."""
    interaction = press()

    await cog.handle(interaction.as_interaction(), IDS.parse(NEW_ID))

    [embed] = shown(interaction)
    assert [field["value"] for field in embed["fields"]] == ["0 $", "0 $"]
    assert await store.keys(NAMESPACE) == []  # v3 created the wallet


async def test_outside_a_guild(cog: Economy) -> None:
    """Requirement: Economy buttons show the presser's wallet."""
    interaction = press()
    interaction.guild = None

    await cog.handle(interaction.as_interaction(), IDS.parse(NEW_ID))

    assert interaction.sent == []


async def test_select_menu_or_modal(cog: Economy) -> None:
    """Requirement: Economy buttons show the presser's wallet."""
    select = press(component_type=3)
    modal = FakeInteraction(
        {"custom_id": NEW_ID, "components": []},  # a submission's data has no component type
        type=discord.InteractionType.modal_submit,
        user=BOB,
        guild=GUILD,
    )

    await cog.handle(select.as_interaction(), IDS.parse(NEW_ID))
    await cog.handle(modal.as_interaction(), IDS.parse(NEW_ID))

    assert select.sent == modal.sent == []
