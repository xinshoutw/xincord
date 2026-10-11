"""The registration of the commands that the config lists: v3's five by default."""

from typing import TYPE_CHECKING, Any, cast

import pytest
from discord import app_commands

from discord_fakes import FakeChannel, FakeInteraction, embed_dict
from plugin_fakes import golden

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    import discord

    from conftest import Operator
    from discord_fakes import Sent
    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.custom_commands.cog import CustomCommands

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[CustomCommands, discord.Interaction], Awaitable[None]]

GOLDEN = golden("custom_commands")
NAMES = ("cub-none-card", "tsib-none-card", "ctcb-none-card", "ctcb-remit", "chpytwtp-remit")
RULES = """\
commands:
  - name: rules
    description: Post the rules
    localizations:
      en-US: {name: rules-us, description: Post the rules (US)}
      ja: {name: kisoku}
    permissions: [manage_guild, manage_messages]
"""
RULES_PAYLOAD: dict[str, Any] = {
    "type": 1,
    "name": "rules",
    "description": "Post the rules",
    "options": [],
    "name_localizations": {"en-US": "rules-us", "ja": "kisoku"},
    "description_localizations": {"en-US": "Post the rules (US)"},
    "default_member_permissions": 8224,  # Manage Server (32) and Manage Messages (8192)
}
EVERY_MEMBER = """\
commands:
  - {name: help, description: Show the help, permissions: []}
"""
SOME_GUILDS = """\
commands:
  - {name: shop, description: Open the shop, guilds: [1]}
  - {name: help, description: Show the help}
"""


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists."""
    return {key: actual.get(key) for key in expected}


async def test_command_payload(bot: Bot) -> None:
    """Requirement: Commands come from the config."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: list[dict[str, Any]] = GOLDEN["commands"]
    by_name = {entry["name"]: entry for entry in guild_payload}

    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert [wanted["name"] for wanted in expected] == list(NAMES)
    assert not {entry["name"] for entry in global_payload} & set(NAMES)


@pytest.mark.parametrize("name", NAMES)
async def test_command_callback(bot: Bot, cog: CustomCommands, name: str) -> None:
    """Requirement: Commands come from the config."""
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


async def test_operators_command(operator: Operator) -> None:
    """Requirement: Commands come from the config."""
    operator.template("rules", 'content: "Be nice"\n')
    bot = await operator.load(RULES)

    _, guild_payload = await cast("CommandTree", bot.tree).payloads()

    assert [listed(entry, RULES_PAYLOAD) for entry in guild_payload] == [RULES_PAYLOAD]


async def test_every_member(operator: Operator) -> None:
    """Requirement: Commands come from the config."""
    operator.template("help", 'content: "Ask in #help"\n')
    bot = await operator.load(EVERY_MEMBER)

    _, guild_payload = await cast("CommandTree", bot.tree).payloads()

    assert [(entry["name"], entry["default_member_permissions"]) for entry in guild_payload] == [
        ("help", None)
    ]


async def test_some_guilds(operator: Operator) -> None:
    """Requirement: Commands come from the config."""
    operator.template("shop", 'content: "Welcome"\n')
    operator.template("help", 'content: "Ask in #help"\n')
    bot = await operator.load(SOME_GUILDS)
    tree = cast("CommandTree", bot.tree)

    first, second = (await tree.payloads(1))[1], (await tree.payloads(2))[1]

    assert [entry["name"] for entry in first] == ["shop", "help"]
    assert [entry["name"] for entry in second] == ["help"]
