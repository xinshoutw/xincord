"""The command's handler: the Administrator check, the prompt and its failures.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:59-84
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/en-US/message/ask-message.yaml:1-54
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/zh-TW/message/ask-message.yaml:1-54
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:43-57
"""

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import (
    FakeChannel,
    FakeGuild,
    FakeInteraction,
    FakeMember,
    FakeUser,
    buttons,
    embed_dict,
    forbidden,
)
from plugin_fakes import golden

if TYPE_CHECKING:
    from discord import app_commands

    from xincord.plugins.feedbacker.cog import Feedbacker

GOLDEN = golden("feedbacker")
REPLIES = GOLDEN["config"]
ADMINISTRATOR = discord.Permissions(administrator=True)
EN = discord.Locale.american_english
ZH = discord.Locale.taiwan_chinese


def command(
    guild: FakeGuild,
    *,
    permissions: discord.Permissions = ADMINISTRATOR,
    locale: discord.Locale = EN,
    where: object = None,
) -> FakeInteraction:
    """``/feedbacker`` run by an administrator of ``guild`` in ``where``, else in general (5).

    The guild's locale is zh-TW; ``locale`` is the administrator's.
    """
    interaction = FakeInteraction(
        {"type": 1, "name": "feedbacker"},
        user=FakeMember(guild, id=1, name="admin"),
        guild=guild,
        guild_locale=ZH,
        locale=locale,
        permissions=permissions,
    )
    interaction.channel = FakeChannel(interaction.sent) if where is None else where
    return interaction


def submit_channel(
    channel_type: discord.ChannelType = discord.ChannelType.text,
) -> app_commands.AppCommandChannel:
    """The channel reviews (6) as the ``submit-channel`` option passes it."""
    return cast(
        "app_commands.AppCommandChannel", FakeChannel(id=6, name="reviews", type=channel_type)
    )


async def create(
    cog: Feedbacker,
    interaction: FakeInteraction,
    member: FakeMember | FakeUser,
    channel: app_commands.AppCommandChannel | None = None,
) -> None:
    """Run the command's handler for ``member`` with the submit channel ``channel``."""
    target = cast("discord.Member | discord.User", member)
    await cog.create_form(interaction.as_interaction(), target, channel or submit_channel())


def response(text: str) -> tuple[str, dict[str, object]]:
    """The edit that turns the deferred response into ``text``."""
    return ("edit_original_response", {"content": text})


@pytest.mark.parametrize("locale", [EN, ZH])
async def test_form_posted(cog: Feedbacker, locale: discord.Locale) -> None:
    """Requirement: Administrators post a feedback form."""
    guild = FakeGuild()
    interaction = command(guild, locale=locale)

    await create(cog, interaction, FakeMember(guild, id=7, name="bob"))

    (method, fields), done = interaction.sent
    assert method == "channel.send"
    assert done == response(REPLIES["form_success"])
    embeds = cast("tuple[discord.Embed, ...]", fields["embeds"])
    assert [embed_dict(embed) for embed in embeds] == [GOLDEN["ask"][locale.value]]
    assert fields["content"] is None
    assert fields["files"] == ()
    view = fields["view"]
    assert buttons(view) == [
        (label, f"feedbacker:1:a=submit_star;b=7;d=6;c={count}")
        for count, label in enumerate(GOLDEN["star_labels"], start=1)
    ]
    assert isinstance(view, discord.ui.View)
    assert {cast("discord.ui.Button[discord.ui.View]", item).style for item in view.children} == {
        discord.ButtonStyle.secondary
    }
    assert view.is_finished()  # the core routes its presses, not discord.py


async def test_member_without_administrator(cog: Feedbacker) -> None:
    """Requirement: Only administrators post forms."""
    guild = FakeGuild()
    interaction = command(guild, permissions=discord.Permissions(manage_guild=True))

    await create(cog, interaction, FakeMember(guild, id=7))

    assert interaction.sent == [response(REPLIES["form_no_permission"])]


async def test_not_a_member(cog: Feedbacker, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A form that cannot be posted is reported."""
    interaction = command(FakeGuild())

    with caplog.at_level(logging.WARNING):
        await create(cog, interaction, FakeUser(id=8, name="stranger"))

    assert interaction.sent == [response(REPLIES["form_failure"])]
    assert "stranger (8)" in caplog.text


async def test_not_a_text_channel(cog: Feedbacker, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A form that cannot be posted is reported."""
    guild = FakeGuild()
    interaction = command(guild)
    news = submit_channel(discord.ChannelType.news)

    with caplog.at_level(logging.WARNING):
        await create(cog, interaction, FakeMember(guild, id=7), news)

    assert interaction.sent == [response(REPLIES["form_failure"])]
    assert "reviews (6)" in caplog.text


async def test_channel_refuses_the_form(cog: Feedbacker, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A form that cannot be posted is reported."""
    guild = FakeGuild()
    interaction = command(guild, where=FakeChannel(error=forbidden()))

    with caplog.at_level(logging.WARNING):
        await create(cog, interaction, FakeMember(guild, id=7))

    assert interaction.sent == [response(REPLIES["form_failure"])]
    assert "general (5)" in caplog.text
    assert "Missing Permissions" in caplog.text


async def test_channel_takes_no_messages(cog: Feedbacker, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A form that cannot be posted is reported."""
    guild = FakeGuild()
    forum = SimpleNamespace(id=5, name="forum", type=discord.ChannelType.forum)
    interaction = command(guild, where=forum)

    with caplog.at_level(logging.WARNING):
        await create(cog, interaction, FakeMember(guild, id=7))

    assert interaction.sent == [response(REPLIES["form_failure"])]
    assert "forum (5)" in caplog.text
