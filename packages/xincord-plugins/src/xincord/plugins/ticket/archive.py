"""The archive: a ticket's messages copied into a new thread of another channel, by a webhook.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:378-782
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:854-878
"""

import string
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord

from .channels import InGuild
from .texts import chunks, clip, units

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import tzinfo

    from .channels import (
        ArchivedMessage,
        ArchiveTarget,
        ArchiveThread,
        Author,
        History,
        Webhook,
    )
    from .texts import Texts

MESSAGE_MAX = 2000  # Discord's limit of a message's text
THREAD_NAME_MAX = 100  # Discord's limit of a thread's name, v3's threadNameMaxLength
WEBHOOK_NAME_MAX = 80  # Discord's limit of a webhook's name
NAME_TIME = "%Y-%m-%d_%H:%M:%S"  # v3's threadTimeFormatter
WEBHOOK_PREFIX = "ticket-save-content-"
COUNTER_BITS = 0xFFFFF  # v3 kept the 20 low bits of System.nanoTime()
DIGITS = string.digits + string.ascii_lowercase  # the digits of Java's Long.toString(n, 36)
BASE = len(DIGITS)
# What Discord refuses in a webhook's name: its rules for usernames, and Clyde.
REFUSED_PARTS = ("@", "#", ":", "```", "discord", "clyde")
REFUSED_NAMES = frozenset(("everyone", "here"))
# What a cut never separates from the character before it.
ZWJ = chr(0x200D)  # the zero-width joiner, which joins the characters on both sides
MARKS = frozenset(("Mn", "Me"))  # nonspacing and enclosing marks
VARIATION_SELECTORS = range(0xFE00, 0xFE10)
EMOJI_MODIFIERS = range(0x1F3FB, 0x1F400)


@dataclass(frozen=True)
class Options:
    """What an archive needs besides its channels."""

    texts: Texts  # the markers' texts, in the default locale as v3's
    now: float  # when the archive starts, in seconds since the epoch
    zone: tzinfo | None  # the time zone of the thread's name and the markers; None: the host's
    upload_limit: int  # the guild's upload limit in bytes; larger files are linked


async def archive(source: History, target: ArchiveTarget, options: Options) -> ArchiveThread:
    """Copy ``source``'s messages into a new public thread of ``target``; return the thread.

    v3's steps, one request at a time: the thread, named after the channel and the time, without a
    starter message; a webhook with a name of its own; every message with text or files, oldest
    first; the webhook's deletion.
    """
    thread = await target.create_thread(
        name=thread_name(source.name, options.now, options.zone),
        type=discord.ChannelType.public_thread,
    )
    webhook = await target.create_webhook(
        name=webhook_name(int(options.now * 1000), time.perf_counter_ns())
    )
    await _Copy(webhook, thread, options).channel(source)
    await webhook.delete()
    return thread


@dataclass(frozen=True)
class _Copy:
    """An archive under way: its webhook, its thread and its options."""

    webhook: Webhook
    thread: ArchiveThread
    options: Options

    async def channel(self, source: History) -> None:
        """Forward the channel's messages, oldest first."""
        async for message in source.history(limit=None, oldest_first=True):
            await self.forward(message)

    async def forward(self, message: ArchivedMessage) -> None:
        """Send a message with text or files under its author's name and avatar.

        Others (embeds, stickers, polls, empty system messages) are skipped, as in v3. A text over
        2000 UTF-16 code units goes in parts, the files with the last (v3 hung, B12); a file over
        the guild's upload limit goes as its URL on its own line (v3's upload failed).
        """
        if not message.content and not message.attachments:
            return
        limit = self.options.upload_limit
        attachments = message.attachments
        links = [attachment.url for attachment in attachments if attachment.size > limit]
        files = [
            await attachment.to_file() for attachment in attachments if attachment.size <= limit
        ]
        lines = [message.content, *links] if message.content else links
        *parts, last = chunks("\n".join(lines), MESSAGE_MAX)
        for part in parts:
            await self._send(part, message.author)
        await self._send(last, message.author, files)

    async def _send(self, text: str, author: Author, files: Sequence[discord.File] = ()) -> None:
        """Send ``text`` and ``files`` under the author's name and avatar, pinging nobody (v3
        pinged as the text said, S1)."""
        await self.webhook.send(
            content=text or None,
            username=forwarded_name(author),
            avatar_url=author.display_avatar.url,
            files=files,
            allowed_mentions=discord.AllowedMentions.none(),
            thread=self.thread,
            wait=True,
        )


def thread_name(channel: str, now: float, zone: tzinfo | None) -> str:
    """The archive thread's name, v3's: the channel's name and ``-yyyy-MM-dd_HH:mm:ss`` of
    ``now`` in ``zone`` (None: the host's), the name cut to keep Discord's 100 UTF-16 code units.
    """
    suffix = "-" + datetime.fromtimestamp(now, UTC).astimezone(zone).strftime(NAME_TIME)
    return clip_name(channel, THREAD_NAME_MAX - units(suffix)) + suffix


def clip_name(text: str, limit: int) -> str:
    """The longest start of ``text`` within ``limit`` UTF-16 code units that ends between two
    characters, as v3's ``BreakIterator``: never inside a surrogate pair, never before a mark, a
    variation selector or an emoji modifier, and never next to a zero-width joiner."""
    end = len(clip(text, limit))
    while 0 < end < len(text) and not _breaks(text[end - 1], text[end]):
        end -= 1
    return text[:end]


def _breaks(before: str, after: str) -> bool:
    """Whether a cut between ``before`` and ``after`` keeps the characters whole."""
    if ZWJ in (before, after):
        return False
    point = ord(after)
    return not (
        unicodedata.combining(after)
        or unicodedata.category(after) in MARKS
        or point in VARIATION_SELECTORS
        or point in EMOJI_MODIFIERS
    )


def webhook_name(milliseconds: int, counter: int) -> str:
    """The archive webhook's name, v3's: Java's base 36 of the time in milliseconds and of the
    counter's 20 low bits, so that two archives never share a name."""
    return f"{WEBHOOK_PREFIX}{_base36(milliseconds)}-{_base36(counter & COUNTER_BITS)}"


def _base36(number: int) -> str:
    """A number of zero or more in base 36, as Java's ``Long.toString(number, 36)``."""
    digits = DIGITS[number % BASE]
    while number >= BASE:
        number //= BASE
        digits = DIGITS[number % BASE] + digits
    return digits


def forwarded_name(author: Author) -> str:
    """The name that a message is forwarded under: the first that Discord takes for a webhook of
    the member's display name (v3's ``member?.effectiveName``, when discord.py has the member),
    the username (v3's ``author.name``) and the user's ID; v3's archive failed on a refused name.
    """
    shown = author.display_name if isinstance(author, InGuild) else author.name
    for name in (shown.strip(), author.name.strip()):
        if _taken(name):
            return name
    return str(author.id)


def _taken(name: str) -> bool:
    """Whether Discord takes ``name`` for a webhook: 1 to 80 characters, none of the parts it
    refuses in usernames, and none of its mentions."""
    folded = name.casefold()
    return (
        0 < len(name) <= WEBHOOK_NAME_MAX
        and folded not in REFUSED_NAMES
        and not any(part in folded for part in REFUSED_PARTS)
    )
