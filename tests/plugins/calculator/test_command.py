"""The registration of /basic-calculate.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/command/Register.kt:9-27
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/Event.kt:49-61
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/resources/lang/en-US/register.yaml:1-7
"""

from typing import TYPE_CHECKING, Any, cast

from discord import app_commands

from discord_fakes import FakeChannel, FakeInteraction
from plugin_fakes import golden

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord

    from discord_fakes import Sent
    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.calculator.cog import Calculator

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[Calculator, discord.Interaction, str], Awaitable[None]]

GOLDEN = golden("calculator")
DATA = {
    "type": 1,
    "name": "basic-calculate",
    "options": [{"type": 3, "name": "formula", "value": "1+1"}],
}


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists."""
    return {key: actual.get(key) for key in expected}


async def test_command_payload(bot: Bot) -> None:
    """Requirement: The command is a localized guild command."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: dict[str, Any] = GOLDEN["command"]

    (payload,) = [entry for entry in guild_payload if entry["name"] == expected["name"]]
    assert all(entry["name"] != expected["name"] for entry in global_payload)
    top = {key: value for key, value in expected.items() if key != "options"}
    assert listed(payload, top) == top
    options = zip(payload["options"], expected["options"], strict=True)
    assert [listed(option, wanted) for option, wanted in options] == expected["options"]


async def test_command_callback(bot: Bot, cog: Calculator) -> None:
    """Requirement: The command is a localized guild command."""
    command = bot.tree.get_command("basic-calculate")
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    sent: list[Sent] = []
    interaction = FakeInteraction(DATA, command=command, channel=FakeChannel(sent), sent=sent)

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    await cast("Callback", command.callback)(cog, interaction.as_interaction(), "1+1")

    assert sent[0] == ("response.defer", {"ephemeral": True, "thinking": True})
    assert [method for method, _ in sent[1:]] == ["channel.send", "delete_original_response"]
