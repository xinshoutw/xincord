"""The counter button under the reply."""

from typing import TYPE_CHECKING

import discord
import pytest

from discord_fakes import FakeInteraction, buttons
from plugin_fakes import golden
from xincord.plugins.example.cog import IDS

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.plugins.example.cog import Example

GOLDEN = golden("example")


def press(
    custom_id: str, locale: discord.Locale = discord.Locale.american_english
) -> FakeInteraction:
    """A click on the button whose ID is ``custom_id``."""
    return FakeInteraction(
        {"component_type": 2, "custom_id": custom_id},
        type=discord.InteractionType.component,
        locale=locale,
    )


@pytest.mark.parametrize("locale", [discord.Locale.american_english, discord.Locale.taiwan_chinese])
async def test_press(bot: Bot, locale: discord.Locale) -> None:
    """Requirement: The counter button counts presses."""
    interaction = press("example:1:a=count;b=4", locale)

    await bot.on_interaction(interaction.as_interaction())

    ((method, fields),) = interaction.sent
    assert method == "response.edit_message"
    assert list(fields) == ["view"]  # the embed stays as it was
    label = GOLDEN["counter"][locale.value].format(count=5)
    assert buttons(fields["view"]) == [(label, "example:1:a=count;b=5")]


async def test_other_action(cog: Example) -> None:
    """Requirement: The counter button counts presses."""
    interaction = press("example:1:a=other")

    await cog.count(interaction.as_interaction(), IDS.parse("example:1:a=other"))

    assert interaction.sent == []
