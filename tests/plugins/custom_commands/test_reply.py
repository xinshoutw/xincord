"""Replies: a command answers with a public or an ephemeral reply instead of a post.

v3's commands only posted in the channel:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/SimpleCommand.kt:21-58
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
import pytest
from discord import app_commands

from discord_fakes import FakeChannel, FakeInteraction
from xincord.plugins.custom_commands.cog import CustomCommands

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from conftest import Operator
    from discord_fakes import Sent
    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[CustomCommands, discord.Interaction], Awaitable[None]]

REPLIES = """\
commands:
  - {name: rules, description: Post the rules, reply: public}
  - {name: faq, description: Answer questions, reply: ephemeral}
"""


async def loaded(operator: Operator) -> Bot:
    """A bot with a public and an ephemeral command, whose templates exist in zh-TW and en-US."""
    for name in ("rules", "faq"):
        operator.template(name, f'content: "{name} %user_name%"\n')
        operator.template(name, f'content: "{name} en-US"\n', locale="en-US")
    return await operator.load(REPLIES)


async def invoke(bot: Bot, name: str, locale: discord.Locale) -> list[Sent]:
    """Run command ``name`` as alice in ``locale``, through the command tree's check."""
    command = bot.tree.get_command(name)
    cog = bot.get_cog("CustomCommands")
    assert isinstance(command, app_commands.Command)
    assert isinstance(cog, CustomCommands)
    sent: list[Sent] = []
    data = {"type": 1, "name": name}
    interaction = FakeInteraction(
        data, locale=locale, command=command, channel=FakeChannel(sent), sent=sent
    ).as_interaction()

    assert await cast("CommandTree", bot.tree).interaction_check(interaction)
    await cast("Callback", command.callback)(cog, interaction)
    return sent


@pytest.mark.xfail(strict=True, reason="A command can answer with a public or an ephemeral reply")
async def test_public_reply(operator: Operator) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    bot = await loaded(operator)

    sent = await invoke(bot, "rules", discord.Locale.american_english)

    assert [method for method, _ in sent] == ["response.defer", "edit_original_response"]
    assert sent[0][1] == {"ephemeral": False, "thinking": True}
    assert sent[1][1]["content"] == "rules alice"  # zh-TW, the default locale


@pytest.mark.xfail(strict=True, reason="A command can answer with a public or an ephemeral reply")
async def test_ephemeral_reply(operator: Operator) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    bot = await loaded(operator)

    sent = await invoke(bot, "faq", discord.Locale.american_english)

    assert [method for method, _ in sent] == ["response.defer", "edit_original_response"]
    assert sent[0][1] == {"ephemeral": True, "thinking": True}
    assert sent[1][1]["content"] == "faq en-US"


@pytest.mark.xfail(strict=True, reason="A command can answer with a public or an ephemeral reply")
async def test_ephemeral_fallback(operator: Operator) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    bot = await loaded(operator)

    sent = await invoke(bot, "faq", discord.Locale.japanese)

    assert [method for method, _ in sent] == ["response.defer", "edit_original_response"]
    assert sent[1][1]["content"] == "faq alice"


@pytest.mark.xfail(strict=True, reason="A command can answer with a public or an ephemeral reply")
async def test_unknown_answer(operator: Operator, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    operator.template("faq", 'content: "Ask in #help"\n')

    with caplog.at_level(logging.ERROR):
        bot = await operator.load(
            "commands:\n  - {name: faq, description: Answer questions, reply: dm}\n"
        )

    assert bot.loaded == ()
    assert "commands.0.reply" in caplog.text
