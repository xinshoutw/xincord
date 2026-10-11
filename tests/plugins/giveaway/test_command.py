"""``/create-giveaway``: a localized administrator guild command that opens the builder."""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest
from discord import app_commands

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeMessage, embed_dict
from plugin_fakes import golden
from xincord.plugins.giveaway.cog import Session
from xincord.plugins.giveaway.model import Draft

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.giveaway.cog import Giveaway

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[Giveaway, discord.Interaction], Awaitable[None]]

GOLDEN = golden("giveaway")
NAME = "create-giveaway"


def run(locale: str = "en-US", message_id: int = 43) -> FakeInteraction:
    """Administrator 7 runs the command in guild 10 with a client in ``locale``."""
    guild = FakeGuild(10)
    return FakeInteraction(
        {"type": 1, "name": NAME},
        locale=discord.Locale(locale),
        user=FakeMember(guild, id=7),
        guild=guild,
        permissions=discord.Permissions(administrator=True),
        original=FakeMessage(id=message_id),
    )


def rows(view: object) -> list[list[tuple[str | None, str | None, int]]]:
    """The label, the ID and the style of each button of a rendered view, row by row."""
    assert isinstance(view, discord.ui.View)
    found: dict[int, list[tuple[str | None, str | None, int]]] = {}
    for item in view.children:
        assert isinstance(item, discord.ui.Button)
        found.setdefault(item.row or 0, []).append((item.label, item.custom_id, item.style.value))
    return [found[row] for row in sorted(found)]


def expected_rows(locale: str) -> list[list[tuple[str, str, int]]]:
    """The builder buttons in ``locale``, with the new IDs."""
    builder = GOLDEN["builder"]
    return [
        [
            (label, f"giveaway:1:a=create;b={sub_action}", style)
            for label, sub_action, style in zip(labels, sub_actions, styles, strict=True)
        ]
        for labels, sub_actions, styles in zip(
            builder["labels"][locale], builder["sub-actions"], builder["styles"], strict=True
        )
    ]


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists."""
    return {key: actual.get(key) for key in expected}


async def test_command_payload(bot: Bot) -> None:
    """Requirement: The command is a localized administrator guild command."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: list[dict[str, Any]] = GOLDEN["commands"]

    by_name = {entry["name"]: entry for entry in guild_payload}

    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert NAME not in {entry["name"] for entry in global_payload}


async def test_command_callback(bot: Bot, cog: Giveaway) -> None:
    """Requirement: The command is a localized administrator guild command."""
    command = bot.tree.get_command(NAME)
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    interaction = run()
    interaction.command = command

    assert await cast("CommandTree", bot.tree).interaction_check(interaction.as_interaction())
    callback = cast("Callback", command.callback)
    await callback(cog, interaction.as_interaction())

    (deferred, (edited, _)) = interaction.sent
    assert deferred == ("response.defer", {"ephemeral": True, "thinking": True})
    assert edited == "edit_original_response"


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_builder(cog: Giveaway, locale: str) -> None:
    """Requirement: The command opens the builder."""
    interaction = run(locale)

    await cog.create_giveaway(interaction.as_interaction())

    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    assert fields["content"] == ""  # the template has no content
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    assert embed_dict(embed) == GOLDEN["preview"][locale]["empty"]
    assert rows(fields["view"]) == expected_rows(locale)


@pytest.mark.parametrize(("locale", "shown"), [("en-GB", "en-US"), ("zh-CN", "zh-TW")])
async def test_builder_language(cog: Giveaway, locale: str, shown: str) -> None:
    """Requirement: The command opens the builder."""
    interaction = run(locale)

    await cog.create_giveaway(interaction.as_interaction())

    [(_, fields)] = interaction.sent
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    # The preview's texts and the buttons' labels in one language.
    assert embed_dict(embed) == GOLDEN["preview"][shown]["empty"]
    assert rows(fields["view"]) == expected_rows(shown)


async def test_new_draft(cog: Giveaway) -> None:
    """Requirement: The command opens the builder."""
    await cog.create_giveaway(run(message_id=43).as_interaction())
    cog.drafts[7, 10] = Session(43, Draft(title="Old"))

    await cog.create_giveaway(run(message_id=44).as_interaction())

    assert cog.drafts == {(7, 10): Session(44, Draft())}


async def test_outside_guild(cog: Giveaway) -> None:
    """Requirement: The command opens the builder."""
    interaction = run()
    interaction.guild = None  # a guild command never runs there

    await cog.create_giveaway(interaction.as_interaction())

    assert interaction.sent == []
    assert cog.drafts == {}
