"""The answer: an embed in the channel, then the deferred response is deleted.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:48-60
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/resources/lang/en-US/message/basic-calculate.yaml:1-14
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/resources/lang/zh-TW/message/basic-calculate.yaml:1-14
"""

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeInteraction, embed_dict, forbidden
from plugin_fakes import golden, load_plugin
from xincord.plugins.basic_calculator.cog import BasicCalculator

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from discord_fakes import Sent
    from xincord.core.storage import Store

GOLDEN = golden("basic_calculator")
TEMPLATE = 'content: "%user_name%: %bc_question% = %bc_answer% (%bc_answer_round%)"\n'


def command(formula: str, locale: discord.Locale, channel: object) -> FakeInteraction:
    """The command interaction for ``formula``, sharing its record with a fake channel's."""
    data = {
        "type": 1,
        "name": "basic-calculate",
        "options": [{"type": 3, "name": "formula", "value": formula}],
    }
    sent: list[Sent] = channel.sent if isinstance(channel, FakeChannel) else []
    return FakeInteraction(data, locale=locale, channel=channel, sent=sent)


async def run(
    cog: BasicCalculator,
    formula: str,
    *,
    locale: discord.Locale = discord.Locale.american_english,
    channel: object = None,
) -> list[Sent]:
    """Run the command as alice in a fake channel; return what the plugin sent, in order."""
    interaction = command(formula, locale, FakeChannel() if channel is None else channel)
    await cog.basic_calculate(interaction.as_interaction(), formula)
    return interaction.sent


def embeds(fields: dict[str, object]) -> list[dict[str, Any]]:
    """The embeds of a message, as dictionaries."""
    return [embed_dict(embed) for embed in cast("Sequence[discord.Embed]", fields["embeds"])]


async def test_answer(cog: BasicCalculator) -> None:
    """Requirement: The answer is posted in the channel."""
    sent = await run(cog, "1+1 = ?")

    assert [method for method, _ in sent] == ["channel.send", "delete_original_response"]
    assert embeds(sent[0][1]) == [GOLDEN["answer"]["en-US"]]


@pytest.mark.parametrize("locale", [discord.Locale.taiwan_chinese, discord.Locale.japanese])
async def test_locale_and_fallback(cog: BasicCalculator, locale: discord.Locale) -> None:
    """Requirement: The answer is posted in the channel."""
    sent = await run(cog, "1+1 = ?", locale=locale)

    assert embeds(sent[0][1]) == [GOLDEN["answer"]["zh-TW"]]


@pytest.mark.parametrize(
    ("formula", "content"),
    [
        ("-7/2", "alice: -7/2 = -3.5 (-3)"),
        ("-1/2", "alice: -1/2 = -0.5 (0)"),
        ("10/4=", "alice: 10/4 = 2.5 (2)"),
        ("2^10", "alice: 2^10 = 1024 (1024)"),
    ],
)
async def test_placeholders(store: Store, tmp_path: Path, formula: str, content: str) -> None:
    """Requirement: The answer is posted in the channel."""
    message = tmp_path / "plugins" / "BasicCalculator" / "lang" / "en-US" / "message"
    message.mkdir(parents=True)
    (message / "basic-calculate.yaml").write_text(TEMPLATE, encoding="utf-8")
    bot = await load_plugin("BasicCalculator", tmp_path / "plugins", store)
    cog = bot.get_cog("BasicCalculator")
    assert isinstance(cog, BasicCalculator)

    sent = await run(cog, formula)

    assert sent[0][1]["content"] == content


async def test_channel_refuses_the_message(
    cog: BasicCalculator, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The answer is posted in the channel."""
    with caplog.at_level(logging.WARNING):
        sent = await run(cog, "1+1 = ?", channel=FakeChannel(error=forbidden()))

    assert [method for method, _ in sent] == ["edit_original_response"]
    assert embeds(sent[0][1]) == [GOLDEN["answer"]["en-US"]]
    assert "cannot post" in caplog.text


async def test_channel_without_messages(cog: BasicCalculator) -> None:
    """Requirement: The answer is posted in the channel."""
    forum = SimpleNamespace(id=6, name="questions")  # a forum or a category has no send

    sent = await run(cog, "1+1 = ?", channel=forum)

    assert [method for method, _ in sent] == ["edit_original_response"]
    assert embeds(sent[0][1]) == [GOLDEN["answer"]["en-US"]]
