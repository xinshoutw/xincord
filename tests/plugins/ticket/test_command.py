"""``/create-ticket`` and ``/add-ticket``: localized administrator guild commands; the first opens
the builder of a new panel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/command/Register.kt:11-43
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/command/CmdFileSerializer.kt:7-27
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Event.kt:53-65
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:20-31
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:29-51
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:181-196
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/resources/lang/en-US/message/create-ticket.yaml:1-65
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest
from discord import app_commands

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeMessage, embed_dict
from plugin_fakes import golden
from xincord.plugins.ticket.cog import IDS, Session
from xincord.plugins.ticket.model import Draft

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.plugins.ticket.cog import Ticket

    # discord.py calls a cog command's function with the cog, its binding.
    type Callback = Callable[[Ticket, discord.Interaction], Awaitable[None]]

GOLDEN = golden("ticket")
NAME = "create-ticket"
PREVIEW = IDS.build({"action": "create", "sub_action": "prev"})


def run(locale: str = "en-US", message_id: int = 43) -> FakeInteraction:
    """Administrator 7 runs ``/create-ticket`` in guild 10 with a client in ``locale``."""
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


def expected_rows(name: str, locale: str) -> list[list[tuple[str | None, str | None, int]]]:
    """v3's builder ``name`` in ``locale`` under the preview button of a new draft, new IDs."""
    builder = GOLDEN["builder"][name]
    preview: tuple[str | None, str | None, int] = (GOLDEN["preview"][locale]["button"], PREVIEW, 3)
    buttons: list[list[tuple[str | None, str | None, int]]] = [
        [
            (label, IDS.build({"action": "create", "sub_action": sub_action}), style)
            for label, sub_action, style in zip(labels, sub_actions, styles, strict=True)
        ]
        for labels, sub_actions, styles in zip(
            builder["labels"][locale], builder["sub-actions"], builder["styles"], strict=True
        )
    ]
    return [[preview], *buttons]


def listed(actual: object, expected: object) -> object:
    """``actual`` with only the keys that ``expected`` lists, in lists and objects too."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        wanted = cast("dict[str, Any]", expected)
        found = cast("dict[str, Any]", actual)
        return {key: listed(found.get(key), value) for key, value in wanted.items()}
    if isinstance(expected, list) and isinstance(actual, list):
        wanted_items = cast("list[Any]", expected)
        found_items = cast("list[Any]", actual)
        return [
            listed(item, wanted) for item, wanted in zip(found_items, wanted_items, strict=False)
        ] + found_items[len(wanted_items) :]
    return actual


async def test_command_payloads(bot: Bot) -> None:
    """Requirement: The commands are localized administrator guild commands."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()

    expected: list[dict[str, Any]] = GOLDEN["commands"]
    by_name = {entry["name"]: entry for entry in guild_payload}
    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert not {NAME, "add-ticket"} & {entry["name"] for entry in global_payload}


async def test_command_callback(bot: Bot, cog: Ticket) -> None:
    """Requirement: The commands are localized administrator guild commands."""
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
async def test_builder(cog: Ticket, locale: str) -> None:
    """Requirement: The create command opens the builder."""
    interaction = run(locale)

    await cog.create_ticket(interaction.as_interaction())

    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    assert fields["content"] == ""  # the template has no content
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    assert embed_dict(embed) == GOLDEN["preview"][locale]["embed"]
    assert rows(fields["view"]) == expected_rows(NAME, locale)


async def test_new_draft(cog: Ticket) -> None:
    """Requirement: The create command opens the builder."""
    await cog.create_ticket(run("zh-TW", message_id=43).as_interaction())
    cog.drafts[7, 10] = Session(43, Draft("Old"))

    await cog.create_ticket(run("zh-TW", message_id=44).as_interaction())

    [(key, session)] = cog.drafts.items()
    assert key == (7, 10)
    assert session.message_id == 44
    assert session.target is None
    draft = session.draft
    assert draft.reason_title == GOLDEN["preview"]["zh-TW"]["reason-title"]
    assert (draft.color, draft.button_style, draft.admin_ids, draft.category_id) == (
        0x00FFFF,
        3,
        (),
        0,
    )
    assert draft.button_emoji == chr(0x2709)  # v3's envelope, without a variation selector


async def test_outside_guild(cog: Ticket) -> None:
    """Requirement: The create command opens the builder."""
    interaction = run()
    interaction.guild = None  # a guild command never runs there

    await cog.create_ticket(interaction.as_interaction())

    assert interaction.sent == []
    assert cog.drafts == {}
