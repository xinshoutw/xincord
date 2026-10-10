"""What v3 built in its code: the preview, the panel button, the control row and the save select.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:145-176
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:211-226
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:784-832
"""

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from xincord.core.templates import IdBuilder

    from .model import Controls, Draft
    from .texts import Texts


def preview_embed(draft: Draft) -> discord.Embed:
    """The panel's embed, v3's ``previewEmbed`` of a new panel: unset parts left out.

    As JDA's ``setAuthor(null, ...)``, the icon goes with the author.
    """
    embed = discord.Embed(
        title=draft.title or None, description=draft.description or None, color=draft.color
    )
    if draft.author:
        embed.set_author(name=draft.author, icon_url=draft.author_icon_url or None)
    return embed


def preview_button(draft: Draft, build_id: IdBuilder) -> discord.ui.Button[discord.ui.View]:
    """The builder's preview of the panel button, which opens the reason modal's preview.

    v3's preview button had no action, so pressing it failed (B1).
    """
    return _button(draft, build_id({"action": "create", "sub_action": "prev"}))


def _button(draft: Draft, custom_id: str) -> discord.ui.Button[discord.ui.View]:
    """A button with the draft's style, label and emoji, as v3's ``Button.of``."""
    return discord.ui.Button[discord.ui.View](
        style=discord.ButtonStyle(draft.button_style),
        custom_id=custom_id,
        label=draft.button_text or None,
        emoji=discord.PartialEmoji.from_str(draft.button_emoji) if draft.button_emoji else None,
    )


def panel_button(
    draft: Draft, index: int, build_id: IdBuilder
) -> discord.ui.Button[discord.ui.View]:
    """The panel's button ``index``, v3's ``buildTicketButton``: it opens the reason modal."""
    return _button(draft, build_id({"action": "press", "btn_index": str(index)}))


def control_row(
    controls: Controls, *, locked: bool, texts: Texts, build_id: IdBuilder
) -> discord.ui.View:
    """A ticket channel's control row, v3's ``buildTicketActionRow``, stopped for the router."""
    raise NotImplementedError
