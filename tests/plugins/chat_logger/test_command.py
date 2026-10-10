"""The registration of ``/chat-logger`` and its subcommand ``setting``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/command/Register.kt:11-33
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/command/CmdFileSerializer.kt:7-23
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:83-95
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/en-US/register.yaml:1-8
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/zh-TW/register.yaml:1-8
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30
"""

from typing import TYPE_CHECKING, Any, cast

import pytest
from discord import app_commands

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember
from plugin_fakes import golden

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.chat_logger.cog import ChatLogger

    # discord.py calls a cog command's function with the cog, its binding, and the options.
    type Callback = Callable[..., Awaitable[None]]

GOLDEN = golden("chat_logger")
NAME = "chat-logger"
GUILD = FakeGuild(10)
REASON = "The command is a localized administrator guild command"


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists, in its options too."""
    found = {key: actual.get(key) for key in expected}
    if "options" in expected:
        options = cast("list[dict[str, Any]]", actual.get("options") or [])
        wanted = cast("list[dict[str, Any]]", expected["options"])
        if len(options) == len(wanted):
            found["options"] = [listed(*pair) for pair in zip(options, wanted, strict=True)]
    return found


@pytest.mark.xfail(strict=True, reason=REASON)
async def test_command_payload(bot: Bot) -> None:
    """Requirement: The command is a localized administrator guild command."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: list[dict[str, Any]] = GOLDEN["commands"]

    by_name = {entry["name"]: entry for entry in guild_payload}

    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert [entry["name"] for entry in guild_payload] == [NAME]  # a guild command
    assert NAME not in {entry["name"] for entry in global_payload}


@pytest.mark.xfail(strict=True, reason=REASON)
async def test_command_callback(bot: Bot, cog: ChatLogger) -> None:
    """Requirement: The command is a localized administrator guild command."""
    group = bot.tree.get_command(NAME)
    assert isinstance(group, app_commands.Group)
    command = group.get_command("setting")
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    data: dict[str, object] = {"type": 1, "name": NAME, "options": [{"type": 1, "name": "setting"}]}
    interaction = FakeInteraction(
        data, command=command, user=FakeMember(GUILD), guild=GUILD, channel=FakeChannel(id=5)
    ).as_interaction()

    assert await cast("CommandTree", bot.tree).interaction_check(interaction)
    await cast("Callback", command.callback)(cog, interaction)

    deferred, (method, _) = cast("FakeInteraction", interaction).sent
    assert deferred == ("response.defer", {"ephemeral": True, "thinking": True})
    assert method == "edit_original_response"
