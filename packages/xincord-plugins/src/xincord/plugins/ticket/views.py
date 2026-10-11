"""The views built in code: the preview, the panel button, the control row and the save select."""

from typing import TYPE_CHECKING

import discord

# The emojis of the control row, without variation selectors.
LOCKED = 0x1F512
UNLOCKED = 0x1F513
FLOPPY = 0x1F4BE
WASTEBASKET = 0x1F5D1

if TYPE_CHECKING:
    from xincord.core.templates import IdBuilder

    from .model import Controls, Draft
    from .texts import Texts


def preview_embed(draft: Draft) -> discord.Embed:
    """The panel's embed of a new panel: unset parts left out.

    The icon goes with the author.
    """
    embed = discord.Embed(
        title=draft.title or None, description=draft.description or None, color=draft.color
    )
    if draft.author:
        embed.set_author(name=draft.author, icon_url=draft.author_icon_url or None)
    return embed


def preview_button(draft: Draft, build_id: IdBuilder) -> discord.ui.Button[discord.ui.View]:
    """The builder's preview of the panel button, which opens the reason modal's preview."""
    return _button(draft, build_id({"action": "create", "sub_action": "prev"}))


def _button(draft: Draft, custom_id: str) -> discord.ui.Button[discord.ui.View]:
    """A button with the draft's style, label and emoji."""
    return discord.ui.Button[discord.ui.View](
        style=discord.ButtonStyle(draft.button_style),
        custom_id=custom_id,
        label=draft.button_text or None,
        emoji=discord.PartialEmoji.from_str(draft.button_emoji) if draft.button_emoji else None,
    )


def panel_button(
    draft: Draft, index: int, build_id: IdBuilder
) -> discord.ui.Button[discord.ui.View]:
    """The panel's button ``index``: it opens the reason modal."""
    return _button(draft, build_id({"action": "press", "btn_index": str(index)}))


def control_row(
    controls: Controls, *, locked: bool, texts: Texts, build_id: IdBuilder
) -> discord.ui.View:
    """A ticket channel's control row, stopped for the router.

    Unlock (green) or lock (gray), save (blue) and delete (red), with their emojis and the labels of
    ``texts``; each ID carries the ticket's member and the panel button's message and index.
    """

    def button(
        action: str, style: discord.ButtonStyle, emoji: int
    ) -> discord.ui.Button[discord.ui.View]:
        custom_id = build_id(
            {
                "action": action,
                "user_id": str(controls.user_id),
                "msg_id": controls.message_id,
                "btn_index": controls.index,
            }
        )
        label = texts.get(f"control.{action}")
        return discord.ui.Button(style=style, custom_id=custom_id, label=label, emoji=chr(emoji))

    view = discord.ui.View(timeout=None)
    if locked:
        view.add_item(button("unlock", discord.ButtonStyle.success, UNLOCKED))
    else:
        view.add_item(button("lock", discord.ButtonStyle.secondary, LOCKED))
    view.add_item(button("save", discord.ButtonStyle.primary, FLOPPY))
    view.add_item(button("delete", discord.ButtonStyle.danger, WASTEBASKET))
    view.stop()  # the router handles its buttons, not discord.py
    return view


def save_select(controls: Controls, texts: Texts, build_id: IdBuilder) -> discord.ui.View:
    """The save button's select: one text channel to save the
    conversation in, its ID carrying the row's fields; stopped for the router."""
    choose = texts.get("reply.choose-channel")
    custom_id = build_id(
        {
            "action": "save",
            "sub_action": "select-channel",
            "user_id": str(controls.user_id),
            "msg_id": controls.message_id,
            "btn_index": controls.index,
        }
    )
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.ChannelSelect[discord.ui.View](
            custom_id=custom_id,
            channel_types=[discord.ChannelType.text],
            placeholder=choose,
            min_values=1,
            max_values=1,
        )
    )
    view.stop()  # the router handles its choices, not discord.py
    return view
