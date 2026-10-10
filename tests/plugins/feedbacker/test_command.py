"""The registration of ``/feedbacker``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/command/Register.kt:10-35
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/command/CmdFileSerializer.kt:7-25
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Event.kt:50-62
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/en-US/register.yaml:1-10
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/zh-TW/register.yaml:1-10
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30
"""

from typing import TYPE_CHECKING, Any, cast

import discord
from discord import app_commands

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember
from plugin_fakes import golden
from xincord.plugins.feedbacker.cog import TextChannelOption

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.feedbacker.cog import Feedbacker

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[Feedbacker, discord.Interaction, object, object], Awaitable[None]]

GOLDEN = golden("feedbacker")


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists."""
    return {key: actual.get(key) for key in expected}


async def test_command_payload(bot: Bot) -> None:
    """Requirement: The command is a localized guild command."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: dict[str, Any] = dict(GOLDEN["command"])
    expected_options: list[dict[str, Any]] = expected.pop("options")
    by_name = {entry["name"]: entry for entry in guild_payload}

    actual = by_name.get("feedbacker", {})
    assert listed(actual, expected) == expected
    options = cast("list[dict[str, Any]]", actual["options"])
    pairs = zip(options, expected_options, strict=True)
    assert [listed(option, wanted) for option, wanted in pairs] == expected_options
    assert "feedbacker" not in {entry["name"] for entry in global_payload}


async def test_command_callback(bot: Bot, cog: Feedbacker) -> None:
    """Requirement: The command is a localized guild command."""
    command = bot.tree.get_command("feedbacker")
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    guild = FakeGuild()
    interaction = FakeInteraction(
        {"type": 1, "name": "feedbacker"},
        command=command,
        user=FakeMember(guild),
        guild=guild,
        permissions=discord.Permissions(administrator=True),
    )
    interaction.channel = FakeChannel(interaction.sent)
    submit_channel = FakeChannel(id=6, name="reviews")

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    callback = cast("Callback", command.callback)
    await callback(cog, interaction.as_interaction(), FakeMember(guild, id=7), submit_channel)

    deferred, (posted, _), done = interaction.sent
    assert deferred == ("response.defer", {"ephemeral": True, "thinking": True})
    assert posted == "channel.send"
    assert done == ("edit_original_response", {"content": GOLDEN["config"]["form_success"]})


async def test_text_channels_only() -> None:
    """Requirement: The command is a localized guild command."""
    option = TextChannelOption()
    resolved = FakeChannel(id=6, name="reviews")
    interaction = FakeInteraction({"type": 1, "name": "feedbacker"})

    passed = await option.transform(interaction.as_interaction(), resolved)

    assert passed is resolved
    assert option.type is discord.AppCommandOptionType.channel
    assert option.channel_types == [discord.ChannelType.text]
