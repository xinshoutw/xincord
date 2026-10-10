"""The registration of the five commands.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/Register.kt:9-60
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:49-61
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/register.yaml:1-19
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30
"""

from typing import TYPE_CHECKING, Any, cast

import pytest
from discord import app_commands

from discord_fakes import FakeChannel, FakeInteraction, embed_dict
from plugin_fakes import golden

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    import discord

    from discord_fakes import Sent
    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.simple_command.cog import SimpleCommand

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[SimpleCommand, discord.Interaction], Awaitable[None]]

GOLDEN = golden("simple_command")
NAMES = ("cub-none-card", "tsib-none-card", "ctcb-none-card", "ctcb-remit", "chpytwtp-remit")


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists."""
    return {key: actual.get(key) for key in expected}


async def test_command_payload(bot: Bot) -> None:
    """Requirement: The commands are localized administrator guild commands."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: list[dict[str, Any]] = GOLDEN["commands"]
    by_name = {entry["name"]: entry for entry in guild_payload}

    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert [wanted["name"] for wanted in expected] == list(NAMES)
    assert not {entry["name"] for entry in global_payload} & set(NAMES)


@pytest.mark.parametrize("name", NAMES)
async def test_command_callback(bot: Bot, cog: SimpleCommand, name: str) -> None:
    """Requirement: The commands are localized administrator guild commands."""
    command = bot.tree.get_command(name)
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    sent: list[Sent] = []
    data = {"type": 1, "name": name}
    interaction = FakeInteraction(data, command=command, channel=FakeChannel(sent), sent=sent)

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    await cast("Callback", command.callback)(cog, interaction.as_interaction())

    assert sent[0] == ("response.defer", {"ephemeral": True, "thinking": True})
    assert [method for method, _ in sent[1:]] == ["channel.send", "delete_original_response"]
    embeds = cast("Sequence[discord.Embed]", sent[1][1]["embeds"])
    assert [embed_dict(embed) for embed in embeds] == [GOLDEN["messages"][name]]
