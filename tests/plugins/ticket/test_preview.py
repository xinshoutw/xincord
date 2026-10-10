"""The builder's preview of a draft.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:145-162
"""

import discord

from discord_fakes import embed_dict
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.model import Draft
from xincord.plugins.ticket.views import preview_button, preview_embed

RED = 4
CUSTOM = "<:ticket:123456789012345678>"  # a custom emoji, which v3's Emoji.fromUnicode broke


def test_preview_of_a_draft() -> None:
    """Requirement: The preview shows the draft."""
    draft = Draft(
        "Why?", author="Shop", title="Help", color=0x123456, button_text="Open", button_style=RED
    )

    embed = preview_embed(draft)
    button = preview_button(draft, IDS.build)

    assert embed_dict(embed) == {"author": {"name": "Shop"}, "title": "Help", "color": 0x123456}
    assert button.style is discord.ButtonStyle.danger
    assert button.label == "Open"
    assert button.emoji is None
    # v3's preview button had no action, so pressing it failed (B1); it opens the reason modal.
    assert button.custom_id == IDS.build({"action": "create", "sub_action": "prev"})


def test_preview_with_icon_description_and_emoji() -> None:
    """Requirement: The preview shows the draft."""
    draft = Draft(
        "Why?",
        author="Shop",
        author_icon_url="https://cdn.example/icon.png",
        description="Press below",
        button_emoji=CUSTOM,
    )

    embed = preview_embed(draft)
    button = preview_button(draft, IDS.build)

    assert embed_dict(embed) == {
        "author": {"name": "Shop", "icon_url": "https://cdn.example/icon.png"},
        "description": "Press below",
        "color": 0x00FFFF,
    }
    assert button.style is discord.ButtonStyle.success
    assert button.label is None
    assert str(button.emoji) == CUSTOM


def test_icon_without_author() -> None:
    """Requirement: The preview shows the draft."""
    # JDA's setAuthor(null, ...) dropped the icon with the author.
    embed = preview_embed(Draft("Why?", author_icon_url="https://cdn.example/icon.png", title="T"))

    assert embed_dict(embed) == {"title": "T", "color": 0x00FFFF}
