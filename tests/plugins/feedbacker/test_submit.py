"""A submitted modal: the review in the submit channel, the form's deletion and the failures.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:93-98
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:139-160
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/en-US/message/print-result.yaml:1-12
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/zh-TW/message/print-result.yaml:1-12
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import (
    FakeChannel,
    FakeGuild,
    FakeInteraction,
    FakeMember,
    FakeMessage,
    embed_dict,
    forbidden,
    not_found,
)
from plugin_fakes import golden
from xincord.plugins.feedbacker.cog import IDS

if TYPE_CHECKING:
    from xincord.plugins.feedbacker.cog import Feedbacker

GOLDEN = golden("feedbacker")
REPLIES = GOLDEN["config"]
EN = discord.Locale.american_english
ZH = discord.Locale.taiwan_chinese
DEFERRED = ("response.defer", {"ephemeral": False, "thinking": False})
DELETED: tuple[str, dict[str, object]] = ("message.delete", {})
XFAIL = pytest.mark.xfail(strict=True, raises=NotImplementedError)


def submission(
    feedback: str = "great",
    *,
    count: object = 3,
    guild_locale: discord.Locale = EN,
    channel_type: discord.ChannelType | None = discord.ChannelType.text,
    channel_error: Exception | None = None,
) -> FakeInteraction:
    """Member 7 (alice) submits ``feedback`` with ``count`` stars for submit channel 6.

    alice's client is in zh-TW and the guild's locale is ``guild_locale``. Channel 6, reviews, is
    of ``channel_type``, or gone with None, and fails with ``channel_error``.
    """
    text_input = {"type": 4, "id": 2, "custom_id": "form", "value": feedback}
    interaction = FakeInteraction(
        {
            "custom_id": f"feedbacker:1:a=submit_form;c={count};d=6",
            "components": [{"type": 18, "id": 1, "component": text_input}],
        },
        type=discord.InteractionType.modal_submit,
        locale=ZH,
        guild_locale=guild_locale,
    )
    channels = (
        []
        if channel_type is None
        else [FakeChannel(interaction.sent, channel_error, 6, "reviews", channel_type)]
    )
    guild = FakeGuild(channels=channels)
    interaction.guild = guild
    interaction.user = FakeMember(guild, id=7, name="alice")
    interaction.message = FakeMessage(sent=interaction.sent)
    return interaction


async def run(cog: Feedbacker, interaction: FakeInteraction) -> None:
    """Hand the submission to the plugin, as the core's routing does."""
    custom_id = cast("str", interaction.data["custom_id"])
    await cog.submit_form(interaction.as_interaction(), IDS.parse(custom_id).fields)


def review(interaction: FakeInteraction) -> dict[str, object]:
    """The embed that the submission posted in the submit channel."""
    posts = [fields for method, fields in interaction.sent if method == "channel.send"]
    assert len(posts) == 1
    (post,) = posts
    assert (post["content"], post["view"], post["files"]) == (None, None, ())
    (embed,) = cast("tuple[discord.Embed, ...]", post["embeds"])
    return embed_dict(embed)


def failure() -> tuple[str, dict[str, object]]:
    """The ephemeral follow-up that tells the member the review was not posted."""
    return ("followup.send", {"content": REPLIES["form_submit_failure"], "ephemeral": True})


@XFAIL(reason="A submitted feedback is posted")
@pytest.mark.parametrize("locale", [EN, ZH])
async def test_feedback_posted(cog: Feedbacker, locale: discord.Locale) -> None:
    """Requirement: A submitted feedback is posted."""
    interaction = submission(guild_locale=locale)

    await run(cog, interaction)

    assert review(interaction) == GOLDEN["review"][locale.value]
    deferred, (posted, _), deleted = interaction.sent
    assert (deferred, posted, deleted) == (DEFERRED, "channel.send", DELETED)


@XFAIL(reason="A submitted feedback is posted")
async def test_empty_feedback(cog: Feedbacker) -> None:
    """Requirement: A submitted feedback is posted."""
    interaction = submission("")

    await run(cog, interaction)

    fields = cast("list[dict[str, object]]", review(interaction)["fields"])
    assert fields[0]["value"] == chr(0x200E)  # JDA's stand-in for an empty field
    assert interaction.sent[-1] == DELETED


@XFAIL(reason="A submitted feedback is posted")
async def test_placeholders_in_the_feedback(cog: Feedbacker) -> None:
    """Requirement: A submitted feedback is posted."""
    interaction = submission("%user_id% %fb_content%")

    await run(cog, interaction)

    fields = cast("list[dict[str, object]]", review(interaction)["fields"])
    assert fields[0]["value"] == "%user_id% %fb_content%"


@XFAIL(reason="A submitted feedback is posted")
async def test_form_already_gone(cog: Feedbacker, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A submitted feedback is posted."""
    interaction = submission()
    cast("FakeMessage", interaction.message).error = not_found()

    with caplog.at_level(logging.WARNING):
        await run(cog, interaction)

    assert review(interaction) == GOLDEN["review"]["en-US"]
    assert interaction.sent[0] == DEFERRED
    assert DELETED not in interaction.sent
    assert "form 42" in caplog.text
    assert "Unknown Message" in caplog.text


@XFAIL(reason="A feedback that cannot be posted keeps the form")
@pytest.mark.parametrize(
    "channel_type", [None, discord.ChannelType.news, discord.ChannelType.voice]
)
async def test_channel_gone(
    cog: Feedbacker,
    channel_type: discord.ChannelType | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: A feedback that cannot be posted keeps the form."""
    interaction = submission(channel_type=channel_type)

    with caplog.at_level(logging.WARNING):
        await run(cog, interaction)

    assert interaction.sent == [DEFERRED, failure()]
    assert "channel 6" in caplog.text


@XFAIL(reason="A feedback that cannot be posted keeps the form")
async def test_channel_refuses_the_review(
    cog: Feedbacker, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: A feedback that cannot be posted keeps the form."""
    interaction = submission(channel_error=forbidden())

    with caplog.at_level(logging.WARNING):
        await run(cog, interaction)

    assert interaction.sent == [DEFERRED, failure()]
    assert "reviews (6)" in caplog.text
    assert "Missing Permissions" in caplog.text


@XFAIL(reason="Stars follow v3's text")
@pytest.mark.parametrize("count", ["6", "x"])
async def test_invalid_star_count_fails_the_submission(cog: Feedbacker, count: str) -> None:
    """Requirement: Stars follow v3's text."""
    interaction = submission(count=count)

    with pytest.raises(ValueError, match="star count"):
        await run(cog, interaction)

    assert interaction.sent == []
