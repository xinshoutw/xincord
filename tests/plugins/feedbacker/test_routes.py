"""Routing a form's star presses and submissions, in v3's ID format too.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Event.kt:64-74
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:24-32
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:86-98
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/info.yaml:10
"""

from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember, FakeMessage
from xincord.plugins.feedbacker.cog import IDS

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload

    from discord_fakes import Sent
    from xincord.core.bot import Bot
    from xincord.plugins.feedbacker.cog import Feedbacker

V3_STAR = "feedbacker@a:submit_star;b:7;d:6;c:{count}"  # inventory section 4, as v3 emitted it
NEW_STAR = "feedbacker:1:a=submit_star;b=7;d=6;c={count}"
COMPONENT = discord.InteractionType.component
MODAL = discord.InteractionType.modal_submit
ROUTED = pytest.mark.xfail(strict=True, reason="v3's forms keep working")


def form(star_ids: str, sent: list[Sent]) -> FakeMessage:
    """Member 7's form, whose five star buttons have the IDs ``star_ids`` with each count."""
    stars = [
        {"type": 2, "style": 2, "custom_id": star_ids.format(count=count), "label": "*" * count}
        for count in range(1, 6)
    ]
    payload = cast("ActionRowPayload", {"type": 1, "components": stars})
    return FakeMessage([discord.ActionRow(payload)], sent)


def press(custom_id: str, star_ids: str) -> FakeInteraction:
    """Member 7 presses the button ``custom_id`` of a form whose stars have ``star_ids``."""
    guild = FakeGuild()
    interaction = FakeInteraction(
        {"component_type": 2, "custom_id": custom_id},
        type=COMPONENT,
        user=FakeMember(guild, id=7),
        guild=guild,
    )
    interaction.message = form(star_ids, interaction.sent)
    return interaction


def submit(custom_id: str, star_ids: str) -> FakeInteraction:
    """Member 7 submits ``great`` in the modal ``custom_id`` of a form with ``star_ids``."""
    text_input = {"type": 4, "id": 2, "custom_id": "form", "value": "great"}
    interaction = FakeInteraction(
        {"custom_id": custom_id, "components": [{"type": 18, "id": 1, "component": text_input}]},
        type=MODAL,
        guild_locale=discord.Locale.american_english,
    )
    guild = FakeGuild(channels=[FakeChannel(interaction.sent, id=6, name="reviews")])
    interaction.guild = guild
    interaction.user = FakeMember(guild, id=7)
    interaction.message = form(star_ids, interaction.sent)
    return interaction


def methods(interaction: FakeInteraction) -> list[str]:
    """What the plugin and the core sent, in order."""
    return [method for method, _ in interaction.sent]


def star_ids(view: object) -> list[str | None]:
    """The IDs of the buttons in ``view``."""
    assert isinstance(view, discord.ui.View)
    return [item.custom_id for item in view.children if isinstance(item, discord.ui.Button)]


@ROUTED
async def test_v3_star_button(bot: Bot) -> None:
    """Requirement: v3's forms keep working."""
    interaction = press(V3_STAR.format(count=3), V3_STAR)

    await bot.on_interaction(interaction.as_interaction())

    assert methods(interaction) == ["response.send_modal", "message.edit", "message.edit"]
    modal = cast("discord.ui.Modal", interaction.sent[0][1]["modal"])
    assert modal.custom_id == "feedbacker:1:a=submit_form;c=3;d=6"
    upgraded = interaction.sent[2][1]["view"]  # the core's upgrade after the handler
    assert star_ids(upgraded) == [NEW_STAR.format(count=count) for count in range(1, 6)]
    assert IDS.upgrade(V3_STAR.format(count=3)) == NEW_STAR.format(count=3)


@ROUTED
async def test_v3_modal(bot: Bot) -> None:
    """Requirement: v3's forms keep working."""
    interaction = submit("feedbacker@a:submit_form;c:3;d:6", V3_STAR)

    await bot.on_interaction(interaction.as_interaction())

    # The core cannot upgrade the deleted form; it logs that.
    assert methods(interaction) == ["response.defer", "channel.send", "message.delete"]
    assert IDS.upgrade("feedbacker@a:submit_form;c:3;d:6") == "feedbacker:1:a=submit_form;c=3;d=6"


@ROUTED
async def test_new_ids(bot: Bot) -> None:
    """Requirement: v3's forms keep working."""
    pressed = press(NEW_STAR.format(count=5), NEW_STAR)
    submitted = submit("feedbacker:1:a=submit_form;c=5;d=6", NEW_STAR)

    await bot.on_interaction(pressed.as_interaction())
    await bot.on_interaction(submitted.as_interaction())

    assert methods(pressed) == ["response.send_modal", "message.edit"]
    assert methods(submitted) == ["response.defer", "channel.send", "message.delete"]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="v3's forms keep working")
@pytest.mark.parametrize(
    ("kind", "custom_id"),
    [
        (COMPONENT, "feedbacker:1:a=other"),
        (COMPONENT, "feedbacker:1:a=submit_form;c=3;d=6"),
        (MODAL, "feedbacker:1:a=submit_star;b=7;d=6;c=3"),
    ],
)
async def test_other_action(cog: Feedbacker, kind: discord.InteractionType, custom_id: str) -> None:
    """Requirement: v3's forms keep working."""
    interaction = FakeInteraction({"custom_id": custom_id}, type=kind)

    await cog.handle(interaction.as_interaction(), IDS.parse(custom_id))

    assert interaction.sent == []
