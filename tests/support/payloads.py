"""Discord payloads for tests that feed discord.py's own parsers and REST answers.

``plugin_fakes.add_guild`` caches a guild built from :func:`guild`, and ``plugin_fakes.gateway``
hands :func:`message` payloads to discord.py's ``MESSAGE_CREATE`` and ``MESSAGE_UPDATE`` parsers,
so that plugins get discord.py's own ``Message``, ``Thread`` and ``Member`` objects.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

type Payload = dict[str, object]

TIMESTAMP = "2026-10-10T00:00:00+00:00"


def user(user_id: int, name: str = "alice", *, bot: bool = False) -> Payload:
    """A user without an avatar: discord.py gives the default one."""
    return {
        "id": str(user_id),
        "username": name,
        "discriminator": "0",
        "global_name": None,
        "avatar": None,
        "bot": bot,
    }


def member(user_id: int, name: str = "alice", *, nick: str | None = None) -> Payload:
    """A guild member, as Discord answers ``GET /guilds/{guild}/members/{user}``."""
    return {"user": user(user_id, name), **_membership(nick)}


def channel(channel_id: int, name: str, *, kind: int = 0, parent_id: int | None = None) -> Payload:
    """A guild channel of type ``kind`` (0 text, 2 voice, 4 category, 15 forum), in a category."""
    payload: Payload = {
        "id": str(channel_id),
        "type": kind,
        "name": name,
        "position": 0,
        "permission_overwrites": [],
    }
    if parent_id is not None:
        payload["parent_id"] = str(parent_id)
    return payload


def thread(thread_id: int, parent_id: int, guild_id: int, name: str = "thread") -> Payload:
    """An active public thread of channel ``parent_id``."""
    return {
        "id": str(thread_id),
        "type": 11,
        "name": name,
        "parent_id": str(parent_id),
        "guild_id": str(guild_id),
        "owner_id": "1",
        "thread_metadata": {
            "archived": False,
            "auto_archive_duration": 1440,
            "archive_timestamp": TIMESTAMP,
            "locked": False,
        },
        "message_count": 0,
        "member_count": 1,
        "rate_limit_per_user": 0,
    }


def guild(
    guild_id: int,
    *,
    channels: Sequence[Payload] = (),
    threads: Sequence[Payload] = (),
    locale: str = "en-US",
) -> Payload:
    """A guild as its ``GUILD_CREATE`` carries it, with its channels and active threads."""
    return {
        "id": str(guild_id),
        "name": "guild",
        "preferred_locale": locale,
        "roles": [],
        "members": [],
        "emojis": [],
        "stickers": [],
        "channels": list(channels),
        "threads": list(threads),
    }


def message(  # noqa: PLR0913 - the parts of a message that tests vary
    message_id: int,
    channel_id: int,
    guild_id: int | None,
    author: Payload,
    content: str = "",
    *,
    embeds: Sequence[Payload] = (),
    webhook_id: int | None = None,
) -> Payload:
    """A message as ``MESSAGE_CREATE`` and ``MESSAGE_UPDATE`` carry it.

    In a guild, a member's message carries its ``member``; a webhook's message has none.
    """
    payload: Payload = {
        "id": str(message_id),
        "channel_id": str(channel_id),
        "author": author,
        "content": content,
        "timestamp": TIMESTAMP,
        "edited_timestamp": None,
        "tts": False,
        "mention_everyone": False,
        "mentions": [],
        "mention_roles": [],
        "attachments": [],
        "embeds": list(embeds),
        "pinned": False,
        "type": 0,
    }
    if guild_id is not None:
        payload["guild_id"] = str(guild_id)
        if webhook_id is None:
            payload["member"] = _membership(None)
    if webhook_id is not None:
        payload["webhook_id"] = str(webhook_id)
    return payload


def _membership(nick: str | None) -> Payload:
    """What a member payload adds to its user."""
    return {
        "roles": [],
        "joined_at": "2022-01-01T00:00:00+00:00",
        "deaf": False,
        "mute": False,
        "nick": nick,
        "flags": 0,  # discord.py's Member needs it, or it keeps the author a User
    }
