"""The registration of the four commands.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/command/Register.kt:12-75
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/command/CmdFileSerializer.kt:7-32
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/Event.kt:51-65
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/lang/en-US/register.yaml:1-23
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/resources/lang/zh-TW/register.yaml:1-23
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest
from discord import app_commands

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember
from plugin_fakes import golden
from xincord.plugins.welcome_goodbye.cog import TextChannelOption

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.welcome_goodbye.cog import WelcomeGoodbye

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[WelcomeGoodbye, discord.Interaction], Awaitable[None]]

GOLDEN = golden("welcome_goodbye")
NAMES = ("welcome-channel-bind", "welcome-channel-unbind", "bye-channel-bind", "bye-channel-unbind")


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


@pytest.mark.parametrize(
    ("name", "reply"),
    [
        ("welcome-channel-bind", "welcome-bind-success"),
        ("welcome-channel-unbind", "welcome-unbind-empty"),
        ("bye-channel-bind", "bye-bind-success"),
        ("bye-channel-unbind", "bye-unbind-empty"),
    ],
)
async def test_command_callback(bot: Bot, cog: WelcomeGoodbye, name: str, reply: str) -> None:
    """Requirement: The commands are localized administrator guild commands."""
    command = bot.tree.get_command(name)
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    guild = FakeGuild(10, "guild", channels=[FakeChannel(id=5, name="general")])
    interaction = FakeInteraction(
        {"type": 1, "name": name},
        command=command,
        user=FakeMember(guild),
        channel=guild.get_channel(5),
        guild=guild,
        guild_locale=discord.Locale.american_english,
        permissions=discord.Permissions(administrator=True),
    )

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    await cast("Callback", command.callback)(cog, interaction.as_interaction())

    assert interaction.sent[0] == ("response.defer", {"ephemeral": True, "thinking": True})
    ((method, fields),) = interaction.sent[1:]
    assert method == "edit_original_response"
    assert fields["content"] == GOLDEN["replies"]["en-US"][reply]


async def test_text_channels_only() -> None:
    """Requirement: The commands are localized administrator guild commands."""
    resolved = SimpleNamespace(id=5, name="general", type=discord.ChannelType.text)
    interaction = FakeInteraction({"type": 1, "name": "welcome-channel-bind"})

    passed = await TextChannelOption().transform(interaction.as_interaction(), resolved)

    assert passed is resolved
