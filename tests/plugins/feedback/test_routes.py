"""Routing a form's star presses and submissions, in the legacy ID format too."""

from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember, FakeMessage
from xincord.plugins.feedback.cog import IDS

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload

    from discord_fakes import Sent
    from xincord.core.bot import Bot
    from xincord.plugins.feedback.cog import Feedback

LEGACY_STAR = "feedbacker@a:submit_star;b:7;d:6;c:{count}"  # a legacy form's star
NEW_STAR = "feedback:1:a=submit_star;b=7;d=6;c={count}"
COMPONENT = discord.InteractionType.component
MODAL = discord.InteractionType.modal_submit


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


async def test_legacy_star_button(bot: Bot) -> None:
    """Requirement: Legacy forms keep working."""
    interaction = press(LEGACY_STAR.format(count=3), LEGACY_STAR)

    await bot.on_interaction(interaction.as_interaction())

    assert methods(interaction) == ["response.send_modal", "message.edit", "message.edit"]
    modal = cast("discord.ui.Modal", interaction.sent[0][1]["modal"])
    assert modal.custom_id == "feedback:1:a=submit_form;c=3;d=6"
    upgraded = interaction.sent[2][1]["view"]  # the core's upgrade after the handler
    assert star_ids(upgraded) == [NEW_STAR.format(count=count) for count in range(1, 6)]
    assert IDS.upgrade(LEGACY_STAR.format(count=3)) == NEW_STAR.format(count=3)


async def test_legacy_modal(bot: Bot) -> None:
    """Requirement: Legacy forms keep working."""
    interaction = submit("feedbacker@a:submit_form;c:3;d:6", LEGACY_STAR)

    await bot.on_interaction(interaction.as_interaction())

    # The core cannot upgrade the deleted form; it logs that.
    assert methods(interaction) == ["response.defer", "channel.send", "message.delete"]
    assert IDS.upgrade("feedbacker@a:submit_form;c:3;d:6") == "feedback:1:a=submit_form;c=3;d=6"


async def test_new_ids(bot: Bot) -> None:
    """Requirement: Legacy forms keep working."""
    pressed = press(NEW_STAR.format(count=5), NEW_STAR)
    submitted = submit("feedback:1:a=submit_form;c=5;d=6", NEW_STAR)

    await bot.on_interaction(pressed.as_interaction())
    await bot.on_interaction(submitted.as_interaction())

    assert methods(pressed) == ["response.send_modal", "message.edit"]
    assert methods(submitted) == ["response.defer", "channel.send", "message.delete"]


@pytest.mark.parametrize(
    ("kind", "custom_id"),
    [
        (COMPONENT, "feedback:1:a=other"),
        (COMPONENT, "feedback:1:a=submit_form;c=3;d=6"),
        (MODAL, "feedback:1:a=submit_star;b=7;d=6;c=3"),
    ],
)
async def test_other_action(cog: Feedback, kind: discord.InteractionType, custom_id: str) -> None:
    """Requirement: Legacy forms keep working."""
    interaction = FakeInteraction({"custom_id": custom_id}, type=kind)

    await cog.handle(interaction.as_interaction(), IDS.parse(custom_id))

    assert interaction.sent == []
