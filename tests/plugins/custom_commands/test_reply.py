"""Replies: a command answers with a public or an ephemeral reply instead of a post.

v3's commands only posted in the channel:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/SimpleCommand.kt:21-58
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
import pytest
from discord import app_commands

from discord_fakes import FakeChannel, FakeInteraction, forbidden
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
  - {name: shop, description: Post the shop}
"""


async def loaded(operator: Operator) -> Bot:
    """A bot with a public and an ephemeral command, whose templates exist in zh-TW and en-US."""
    for name in ("rules", "faq", "shop"):
        operator.template(name, f'content: "{name} %user_name%"\n')
        operator.template(name, f'content: "{name} en-US"\n', locale="en-US")
    return await operator.load(REPLIES)


async def invoke(
    bot: Bot, name: str, locale: discord.Locale, *, refused: bool = False
) -> list[Sent]:
    """Run command ``name`` as alice in ``locale``, through the command tree's check.

    ``refused``: Discord refuses the message in the channel and the edit of the response.
    """
    command = bot.tree.get_command(name)
    cog = bot.get_cog("CustomCommands")
    assert isinstance(command, app_commands.Command)
    assert isinstance(cog, CustomCommands)
    sent: list[Sent] = []
    data = {"type": 1, "name": name}
    error = forbidden() if refused else None
    interaction = FakeInteraction(
        data,
        locale=locale,
        command=command,
        channel=FakeChannel(sent, error=error),
        sent=sent,
        edit_error=error,
    ).as_interaction()

    assert await cast("CommandTree", bot.tree).interaction_check(interaction)
    await cast("Callback", command.callback)(cog, interaction)
    return sent


async def test_public_reply(operator: Operator) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    bot = await loaded(operator)

    sent = await invoke(bot, "rules", discord.Locale.american_english)

    assert [method for method, _ in sent] == ["response.defer", "edit_original_response"]
    assert sent[0][1] == {"ephemeral": False, "thinking": True}
    assert sent[1][1]["content"] == "rules alice"  # zh-TW, the default locale


async def test_ephemeral_reply(operator: Operator) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    bot = await loaded(operator)

    sent = await invoke(bot, "faq", discord.Locale.american_english)

    assert [method for method, _ in sent] == ["response.defer", "edit_original_response"]
    assert sent[0][1] == {"ephemeral": True, "thinking": True}
    assert sent[1][1]["content"] == "faq en-US"


async def test_ephemeral_fallback(operator: Operator) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    bot = await loaded(operator)

    sent = await invoke(bot, "faq", discord.Locale.japanese)

    assert [method for method, _ in sent] == ["response.defer", "edit_original_response"]
    assert sent[1][1]["content"] == "faq alice"


@pytest.mark.xfail(strict=True, reason="A command can answer with a public or an ephemeral reply")
@pytest.mark.parametrize(
    ("name", "answer"),
    [("rules", ["response.defer"]), ("shop", ["response.defer"])],
    ids=["public", "post"],
)
async def test_refused_response(
    operator: Operator, caplog: pytest.LogCaptureFixture, name: str, answer: list[str]
) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    bot = await loaded(operator)

    with caplog.at_level(logging.WARNING):
        sent = await invoke(bot, name, discord.Locale.american_english, refused=True)

    # The post goes nowhere and no "thinking" response stays, which a public one would leave in
    # the channel for everyone.
    assert [method for method, _ in sent] == [
        *answer,
        "edit_original_response",
        "delete_original_response",
    ]
    assert f"CustomCommands cannot show {name} in its response" in caplog.text


async def test_unknown_answer(operator: Operator, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A command can answer with a public or an ephemeral reply."""
    operator.template("faq", 'content: "Ask in #help"\n')

    with caplog.at_level(logging.ERROR):
        bot = await operator.load(
            "commands:\n  - {name: faq, description: Answer questions, reply: dm}\n"
        )

    assert bot.loaded == ()
    assert "commands.0.reply" in caplog.text
