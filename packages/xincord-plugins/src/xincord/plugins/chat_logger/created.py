"""A guild message as its ``MESSAGE_CREATE`` payload holds it.

discord.py hands ``on_message`` its cached ``Message``, which a ``MESSAGE_UPDATE`` parsed before the
listener runs changes in place: discord.py parses the frames that arrived together without
yielding. The payload keeps the text that the message was sent with, as JDA's
``MessageReceivedEvent`` did.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import discord

from .text import message_text

if TYPE_CHECKING:
    from discord.types.embed import Embed as EmbedData

EVENT = "MESSAGE_CREATE"  # the gateway event that setup relays
SNOWFLAKE = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class Created:
    """A new guild message: its place, its author and the text it was sent with."""

    message_id: int
    guild_id: int
    channel_id: int
    author_id: int  # a webhook's ID for its messages
    text: str


def parse_created(payload: Mapping[str, object]) -> Created | None:
    """The guild message of a ``MESSAGE_CREATE`` payload, or None for a direct message.

    discord.py parsed the payload before the relay handed it on, so its fields are Discord's; a
    payload without a guild is a direct message's.
    """
    author = payload.get("author")
    fields: Mapping[str, object] = (
        cast("Mapping[str, object]", author) if isinstance(author, Mapping) else {}
    )
    message_id, guild_id, channel_id = (
        _id(payload.get(key)) for key in ("id", "guild_id", "channel_id")
    )
    author_id = _id(fields.get("id"))
    if message_id is None or guild_id is None or channel_id is None or author_id is None:
        return None
    content, embeds = payload.get("content"), payload.get("embeds")
    # Only bots and webhooks send embeds: a member's are link previews (rich ones too).
    sender = fields.get("bot") is True or payload.get("webhook_id") is not None
    entries = cast("list[object]", embeds) if sender and isinstance(embeds, list) else []
    parsed = [
        discord.Embed.from_dict(cast("EmbedData", entry))
        for entry in entries
        if isinstance(entry, Mapping)
    ]
    text = message_text(content if isinstance(content, str) else "", parsed)
    return Created(message_id, guild_id, channel_id, author_id, text)


def _id(value: object) -> int | None:
    """A snowflake of the payload, which Discord sends as a decimal string, or None."""
    return int(value) if isinstance(value, str) and SNOWFLAKE.fullmatch(value) else None
