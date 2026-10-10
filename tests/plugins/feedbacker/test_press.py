"""A star press: who may rate, the feedback modal and the highlight of the pressed star.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:86-137
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/en-US/modal/fill-form.yaml:1-14
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/zh-TW/modal/fill-form.yaml:1-14
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeMessage, forbidden
from plugin_fakes import golden
from xincord.plugins.feedbacker.cog import IDS
from xincord.plugins.feedbacker.form import highlight

if TYPE_CHECKING:
    from discord.types.components import ActionRow as ActionRowPayload
    from discord.types.components import ContainerComponent as ContainerPayload

    from xincord.plugins.feedbacker.cog import Feedbacker

GOLDEN = golden("feedbacker")
REPLIES = GOLDEN["config"]
EN = discord.Locale.american_english
ZH = discord.Locale.taiwan_chinese
PRIMARY = discord.ButtonStyle.primary
SECONDARY = discord.ButtonStyle.secondary


def star_id(count: object) -> str:
    """The ID of a star button of member 7's form, whose submit channel is 6."""
    return f"feedbacker:1:a=submit_star;b=7;d=6;c={count}"


def stars_payload(pressed: int | None = None) -> list[dict[str, object]]:
    """The form's five star buttons, gray but for the ``pressed`` one."""
    return [
        {
            "type": 2,
            "style": PRIMARY.value if count == pressed else SECONDARY.value,
            "custom_id": star_id(count),
            "label": "*" * count,
        }
        for count in range(1, 6)
    ]


def row(*buttons: dict[str, object]) -> discord.Component:
    """An action row of ``buttons``, as discord.py reads it from a message."""
    return discord.ActionRow(cast("ActionRowPayload", {"type": 1, "components": list(buttons)}))


def press(
    count: object,
    *,
    user_id: int = 7,
    locale: discord.Locale = EN,
    pressed: int | None = None,
    error: Exception | None = None,
) -> FakeInteraction:
    """A press of the ``count`` star button of member 7's form by ``user_id``.

    ``pressed`` is the star that an earlier press highlighted; ``error`` makes the form's edits
    fail.
    """
    guild = FakeGuild()
    interaction = FakeInteraction(
        {"component_type": 2, "custom_id": star_id(count)},
        type=discord.InteractionType.component,
        locale=locale,
        user=FakeMember(guild, id=user_id),
        guild=guild,
        guild_locale=ZH,
    )
    interaction.message = FakeMessage([row(*stars_payload(pressed))], interaction.sent, error=error)
    return interaction


async def run(cog: Feedbacker, interaction: FakeInteraction) -> None:
    """Hand the press to the plugin, as the core's routing does."""
    custom_id = cast("str", interaction.data["custom_id"])
    await cog.press_star(interaction.as_interaction(), IDS.parse(custom_id).fields)


def styles(view: object) -> list[tuple[str | None, discord.ButtonStyle]]:
    """The ID and the style of each button in ``view``."""
    assert isinstance(view, discord.ui.View | discord.ui.LayoutView)
    return [
        (item.custom_id, item.style)
        for item in view.walk_children()
        if isinstance(item, discord.ui.Button)
    ]


async def test_someone_else_presses(cog: Feedbacker) -> None:
    """Requirement: Only the rated member presses a star."""
    interaction = press(3, user_id=8)

    await run(cog, interaction)

    reply = {"content": REPLIES["form_not_you"], "ephemeral": True}
    assert interaction.sent == [("response.send_message", reply)]


@pytest.mark.parametrize("locale", [EN, ZH])
async def test_modal_opens(cog: Feedbacker, locale: discord.Locale) -> None:
    """Requirement: A star opens the feedback modal."""
    interaction = press(3, locale=locale)

    await run(cog, interaction)

    (method, fields), _ = interaction.sent
    assert method == "response.send_modal"
    modal = fields["modal"]
    assert isinstance(modal, discord.ui.Modal)
    expected = GOLDEN["modal"][locale.value]
    assert modal.title == expected["title"]
    assert modal.custom_id == "feedbacker:1:a=submit_form;c=3;d=6"
    (label,) = modal.children
    assert isinstance(label, discord.ui.Label)
    assert label.text == expected["label"]
    text_input = label.component
    assert isinstance(text_input, discord.ui.TextInput)
    assert text_input.custom_id == "form"
    assert text_input.style is discord.TextStyle.paragraph
    assert text_input.placeholder == expected["placeholder"]
    assert (text_input.min_length, text_input.max_length) == (None, 1024)
    assert not text_input.required
    assert modal.is_finished()  # the core routes its submission, not discord.py


async def test_pressed_star_highlighted(cog: Feedbacker) -> None:
    """Requirement: A star opens the feedback modal."""
    interaction = press(3, pressed=5)

    await run(cog, interaction)

    (opened, _), (method, fields) = interaction.sent
    assert opened == "response.send_modal"
    assert method == "message.edit"
    assert list(fields) == ["view"]  # the embed stays as it was
    view = fields["view"]
    assert styles(view) == [
        (star_id(count), PRIMARY if count == 3 else SECONDARY) for count in range(1, 6)
    ]
    assert isinstance(view, discord.ui.View)
    assert view.is_finished()


async def test_edit_refused(cog: Feedbacker, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A star opens the feedback modal."""
    interaction = press(3, error=forbidden())

    with caplog.at_level(logging.WARNING):
        await run(cog, interaction)

    ((method, _),) = interaction.sent
    assert method == "response.send_modal"
    assert "message 42" in caplog.text
    assert "Missing Permissions" in caplog.text


async def test_link_buttons_keep_their_style() -> None:
    """Requirement: A star opens the feedback modal."""
    link: dict[str, object] = {"type": 2, "style": 5, "url": "https://example.com", "label": "x"}
    message = FakeMessage([row(*stars_payload()), row(link)])

    view = highlight(message.as_message(), star_id(2))

    assert styles(view)[1] == (star_id(2), PRIMARY)
    assert styles(view)[-1] == (None, discord.ButtonStyle.link)


async def test_components_v2_form() -> None:
    """Requirement: A star opens the feedback modal."""
    container: dict[str, object] = {
        "type": 17,
        "components": [
            {"type": 10, "content": "Please rate us"},
            {"type": 1, "components": stars_payload(pressed=1)},
        ],
    }
    message = FakeMessage(
        [discord.Container(cast("ContainerPayload", container), None)],
        flags=discord.MessageFlags(components_v2=True),
    )

    view = highlight(message.as_message(), star_id(4))

    assert isinstance(view, discord.ui.LayoutView)
    assert [type(item) for item in view.walk_children()][:2] == [
        discord.ui.Container,
        discord.ui.TextDisplay,
    ]
    assert styles(view) == [
        (star_id(count), PRIMARY if count == 4 else SECONDARY) for count in range(1, 6)
    ]
    assert view.is_finished()


async def test_invalid_star_count_fails_the_press(cog: Feedbacker) -> None:
    """Requirement: Stars follow v3's text."""
    interaction = press(6)

    with pytest.raises(ValueError, match="star count"):
        await run(cog, interaction)

    assert interaction.sent == []
