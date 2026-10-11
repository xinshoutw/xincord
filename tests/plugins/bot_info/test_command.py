"""The registration of /bot-info."""

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from discord import app_commands

from discord_fakes import BOT_USER, FakeGuild, FakeInteraction
from plugin_fakes import golden

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.bot_info.cog import BotInfo

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[BotInfo, discord.Interaction], Awaitable[None]]

GOLDEN = golden("bot_info")


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists."""
    return {key: actual.get(key) for key in expected}


async def test_command_payload(bot: Bot) -> None:
    """Requirement: The command is a localized global command."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: dict[str, Any] = GOLDEN["command"]

    (payload,) = [entry for entry in global_payload if entry["name"] == expected["name"]]
    assert all(entry["name"] != expected["name"] for entry in guild_payload)
    assert listed(payload, expected) == expected


async def test_command_callback(bot: Bot, cog: BotInfo) -> None:
    """Requirement: The command is a localized global command."""
    command = bot.tree.get_command("bot-info")
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    client = SimpleNamespace(user=BOT_USER, guilds=[FakeGuild(10, member_count=3)])
    interaction = FakeInteraction({"type": 1, "name": "bot-info"}, client=client, command=command)

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    await cast("Callback", command.callback)(cog, interaction.as_interaction())

    assert interaction.sent[0] == ("response.defer", {"ephemeral": True, "thinking": True})
    assert [method for method, _ in interaction.sent[1:]] == ["edit_original_response"]
