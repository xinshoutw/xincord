"""The registration of the nine guild commands.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/command/Register.kt:11-204
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/command/CmdFileSerializer.kt:7-59
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Event.kt:113-125
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/en-US/register.yaml:1-81
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/zh-TW/register.yaml:1-81
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30
"""

from typing import TYPE_CHECKING, Any, cast

import pytest
from discord import app_commands

from discord_fakes import FakeGuild, FakeInteraction, FakeMember
from plugin_fakes import golden

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.economy.cog import Economy

    # discord.py calls a cog command's function with the cog, its binding, and the options.
    type Callback = Callable[..., Awaitable[None]]

GOLDEN = golden("economy")
NAMES = (
    "balance",
    "top-money",
    "top-cost",
    "add-money",
    "remove-money",
    "set-money",
    "add-cost",
    "remove-cost",
    "set-cost",
)
GUILD = FakeGuild(id=10)
ADMIN = FakeMember(GUILD, id=1, name="admin")  # listed in the conftest's admin_id
BOB = FakeMember(GUILD, id=7, name="bob")
LOCALIZED = "The commands are localized guild commands"


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists, in its options too."""
    found = {key: actual.get(key) for key in expected}
    if "options" in expected:
        options = cast("list[dict[str, Any]]", actual.get("options") or [])
        wanted = cast("list[dict[str, Any]]", expected["options"])
        if len(options) == len(wanted):
            found["options"] = [listed(*pair) for pair in zip(options, wanted, strict=True)]
    return found


@pytest.mark.xfail(strict=True, reason=LOCALIZED)
async def test_command_payloads(bot: Bot) -> None:
    """Requirement: The commands are localized guild commands."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: list[dict[str, Any]] = GOLDEN["commands"]
    by_name = {entry["name"]: entry for entry in guild_payload}

    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert [wanted["name"] for wanted in expected] == list(NAMES)
    assert not {entry["name"] for entry in global_payload} & set(NAMES)


@pytest.mark.xfail(strict=True, reason=LOCALIZED)
@pytest.mark.parametrize("name", NAMES)
async def test_command_callback(bot: Bot, cog: Economy, name: str) -> None:
    """Requirement: The commands are localized guild commands."""
    command = bot.tree.get_command(name)
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    interaction = FakeInteraction(
        {"type": 1, "name": name}, command=command, user=ADMIN, guild=GUILD
    )
    # The options as discord.py passes them: none for the boards, an optional member for balance.
    options = (BOB, 5) if name not in {"balance", "top-money", "top-cost"} else ()

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    await cast("Callback", command.callback)(cog, interaction.as_interaction(), *options)

    deferred, (method, _) = interaction.sent
    assert deferred == ("response.defer", {"ephemeral": True, "thinking": True})
    assert method == "edit_original_response"
