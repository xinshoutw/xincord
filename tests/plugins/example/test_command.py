"""The registration of /example-command."""

from typing import TYPE_CHECKING, Any, cast

from discord import app_commands

from discord_fakes import FakeInteraction
from plugin_fakes import golden

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.example.cog import Example

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[Example, discord.Interaction, str, int | None], Awaitable[None]]

GOLDEN = golden("example")
DATA = {
    "type": 1,
    "name": "example-command",
    "options": [{"type": 3, "name": "option1", "value": "first"}],
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


async def test_command_callback(bot: Bot, cog: Example) -> None:
    """Requirement: The command is a localized guild command."""
    command = bot.tree.get_command("example-command")
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    interaction = FakeInteraction(DATA, command=command)

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    await cast("Callback", command.callback)(cog, interaction.as_interaction(), "first", None)

    assert interaction.sent[0] == ("response.defer", {"ephemeral": True, "thinking": True})
    assert [method for method, _ in interaction.sent[1:]] == ["edit_original_response"]
