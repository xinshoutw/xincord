"""What v3 built in its code: the preview, the panel button, the control row and the save select.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:145-176
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:211-226
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:784-832
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

    from xincord.core.templates import IdBuilder

    from .model import Draft


def preview_embed(draft: Draft) -> discord.Embed:
    """The panel's embed, v3's ``previewEmbed`` of a new panel: unset parts left out."""
    raise NotImplementedError


def preview_button(draft: Draft, build_id: IdBuilder) -> discord.ui.Button[discord.ui.View]:
    """The builder's preview of the panel button, which opens the reason modal's preview."""
    raise NotImplementedError
