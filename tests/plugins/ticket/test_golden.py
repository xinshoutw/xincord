"""v3's texts and IDs: every shipped template renders in each locale, and v3's IDs read."""

from typing import TYPE_CHECKING, Any

import discord
import pytest

from discord_fakes import FakeInteraction, embed_dict
from plugin_fakes import golden
from xincord.core.templates import render_message, render_modal
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.model import Draft
from xincord.plugins.ticket.views import panel_button, preview_button, preview_embed

if TYPE_CHECKING:
    from xincord.plugins.ticket.cog import Ticket

GOLDEN = golden("ticket")
LOCALES = ("en-US", "zh-TW")
DRAFT = Draft("Why?", title="Help", button_text="Open")
# The modals' values, as the builder and the panels fill them; an empty value leaves its input
# empty, as v3's.
VALUES = {
    "tt@author": "Alice",
    "tt@author-icon-url": "https://cdn.example/a.png",
    "tt@title": "Help",
    "tt@description": "Ask us",
    "tt@hex-color": "#00FFFF",
    "tt@btn-text": "Open",
    "tt@btn-emoji": "",
    "tt@reason-title": "Why?",
    "tt@msg-id": "500",
    "tt@btn-index": "0",
    "tt@reason": "Refund",
}


def models() -> dict[str, discord.Embed | discord.ui.Button[discord.ui.View]]:
    """The models that the builder's screens and the panels fill the templates with."""
    return {
        "tt@embed-demo": preview_embed(DRAFT),
        "tt@btn-demo": preview_button(DRAFT, IDS.build),
        "tt@embed": preview_embed(DRAFT),
        "tt@btn": panel_button(DRAFT, 0, IDS.build),
    }


def item(component: discord.ui.Item[discord.ui.View]) -> list[Any]:
    """A button as [button, label, ID, style], a select as [kind, placeholder, ID, min, max], with
    a channel select's types."""
    if isinstance(component, discord.ui.Button):
        return ["button", component.label, component.custom_id, component.style.value]
    if isinstance(component, discord.ui.RoleSelect):
        select: list[Any] = ["role-select"]
    else:
        assert isinstance(component, discord.ui.ChannelSelect)
        select = ["channel-select"]
    select += [
        component.placeholder,
        component.custom_id,
        component.min_values,
        component.max_values,
    ]
    if isinstance(component, discord.ui.ChannelSelect):
        select.append([kind.name for kind in component.channel_types])
    return select


def rows(view: object) -> list[list[list[Any]]]:
    """A rendered view's items, row by row."""
    assert isinstance(view, discord.ui.View)
    found: dict[int, list[list[Any]]] = {}
    for component in view.children:
        found.setdefault(component.row or 0, []).append(item(component))
    return [found[row] for row in sorted(found)]


def builder_rows(name: str, locale: str) -> list[list[list[Any]]]:
    """The rows of a builder screen: the preview button, then the golden builder's buttons."""
    builder = GOLDEN["builder"][name]
    preview = ["button", "Open", IDS.build({"action": "create", "sub_action": "prev"}), 3]
    return [
        [preview],
        *(
            [
                ["button", label, IDS.build({"action": "create", "sub_action": sub}), style]
                for sub, style, label in zip(subs, styles, labels, strict=True)
            ]
            for subs, styles, labels in zip(
                builder["sub-actions"], builder["styles"], builder["labels"][locale], strict=True
            )
        ),
    ]


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize(
    "name",
    [
        "add-ticket",
        "confirm-add",
        "confirm-create",
        "create-ticket",
        "modify-admin-role",
        "modify-btn-color",
        "modify-category",
    ],
)
async def test_message_templates(cog: Ticket, name: str, locale: str) -> None:
    """Requirement: The plugin installs as Ticket."""
    message = render_message(
        cog.templates.message(name, locale), {}, build_id=IDS.build, models=models()
    )

    assert [embed_dict(embed) for embed in message.embeds] == [embed_dict(preview_embed(DRAFT))]
    expected = (
        builder_rows(name, locale)
        if name in GOLDEN["builder"]
        else GOLDEN["messages"][name][locale]
    )
    assert rows(message.view) == expected


def modal_inputs(modal: discord.ui.Modal) -> list[list[Any]]:
    """Each input as [ID, label, style, value, placeholder, min, max, required]."""
    found: list[list[Any]] = []
    for label in modal.children:
        assert isinstance(label, discord.ui.Label)
        text = label.component
        assert isinstance(text, discord.ui.TextInput)
        found.append(
            [
                text.custom_id,
                label.text,
                text.style.name,
                text.default,
                text.placeholder,
                text.min_length,
                text.max_length,
                text.required,
            ]
        )
    return found


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("name", sorted(GOLDEN["modals"]))
async def test_modal_templates(cog: Ticket, name: str, locale: str) -> None:
    """Requirement: The plugin installs as Ticket."""
    modal = render_modal(cog.templates.modal(name, locale), VALUES, build_id=IDS.build)

    expected = GOLDEN["modals"][name][locale]
    assert modal.title == expected["title"]
    assert modal.custom_id == expected["id"]
    assert modal_inputs(modal) == expected["inputs"]


@pytest.mark.parametrize(
    ("v3", "fields", "new"),
    [(shape["v3"], shape["fields"], shape["new"]) for shape in GOLDEN["ids"]],
    ids=[shape["v3"] for shape in GOLDEN["ids"]],
)
def test_v3_ids(v3: str, fields: dict[str, str], new: str) -> None:
    """Requirement: v3's panels and tickets keep working."""
    parsed = IDS.parse(v3)

    assert parsed.legacy
    assert dict(parsed.fields) == fields
    assert IDS.upgrade(v3) == new
    assert IDS.parse(new).fields == parsed.fields


@pytest.mark.parametrize(
    ("locale", "key", "text"),
    [
        (locale, key, text)
        for locale, texts in GOLDEN["v3-texts"].items()
        for key, text in texts.items()
    ],
)
async def test_v3_texts(cog: Ticket, locale: str, key: str, text: str) -> None:
    """Requirement: Texts follow the reader."""
    reader = FakeInteraction({}, locale=discord.Locale(locale))

    assert cog.texts(reader.as_interaction()).get(key) == text
