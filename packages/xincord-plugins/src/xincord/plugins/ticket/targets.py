"""The messages that ``/add-ticket`` adds a button to: found in the command's channel and checked.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:33-51
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepData.kt:106-142
"""

from typing import Protocol, runtime_checkable

import discord

ROW_SIZE = 5  # the components an action row holds at most


@runtime_checkable
class Fetching(Protocol):
    """A channel that fetches its messages, as v3's ``retrieveMessageById``."""

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
    """The message's first action row, v3's ``firstOrNull { it.type == ACTION_ROW }``."""
    return next(
        (component for component in message.components if isinstance(component, discord.ActionRow)),
        None,
    )
