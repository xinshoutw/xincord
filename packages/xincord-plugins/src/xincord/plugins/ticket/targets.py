"""The messages that ``/add-ticket`` adds a button to: found in the command's channel, checked,
and given their view back when the button's entry cannot be stored.
"""

import logging
from typing import Protocol, runtime_checkable

import discord

logger = logging.getLogger(__name__)

ROW_SIZE = 5  # the components an action row holds at most


@runtime_checkable
class Fetching(Protocol):
    """A channel that fetches its messages."""

    async def fetch_message(self, message_id: int, /) -> discord.Message:
        """The channel's message ``message_id``."""
        ...


async def fetch(channel: object, message_id: int) -> discord.Message | None:
    """The channel's message ``message_id``, or None when Discord has none for the bot there."""
    if not isinstance(channel, Fetching):  # a channel without messages has no such message
        return None
    try:
        return await channel.fetch_message(message_id)
    except discord.HTTPException:
        return None


def refusal(message: discord.Message, bot: discord.ClientUser | None) -> str | None:
    """The error key when ``/add-ticket`` cannot add a button to ``message``, else None."""
    if bot is None or message.author.id != bot.id:
        return "error.not-own-message"
    if is_full(message):
        return "error.message-full"
    if not message.embeds:
        return "error.no-embed"
    return None


def is_full(message: discord.Message) -> bool:
    """Whether the message's first action row takes no more button: five components, or a select
    (which fills its row).
    """
    row = first_row(message)
    if row is None:
        return False
    children = row.children
    return len(children) >= ROW_SIZE or not all(
        isinstance(child, discord.Button) for child in children
    )


def first_row(message: discord.Message) -> discord.ActionRow | None:
    """The message's first action row."""
    return next(
        (component for component in message.components if isinstance(component, discord.ActionRow)),
        None,
    )


async def unplace(message: discord.Message) -> None:
    """Give ``message``, as fetched before a button was added to it, its view back: the button's
    entry was not stored. A failure is logged.
    """
    view = discord.ui.View.from_message(message, timeout=None)
    view.stop()  # the router handles its buttons, not discord.py
    try:
        await message.edit(view=view)
    except discord.HTTPException as error:
        logger.warning(
            "Ticket cannot remove the button that it did not store from message %s: %s",
            message.id,
            error,
        )
