"""The archive: a ticket's messages copied into a new thread of another channel, by a webhook.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:378-782
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:854-878
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import tzinfo

    from .channels import ArchiveTarget, ArchiveThread, Author, History
    from .texts import Texts


@dataclass(frozen=True)
class Options:
    """What an archive needs besides its channels."""

    texts: Texts  # the markers' texts, in the default locale as v3's
    now: float  # when the archive starts, in seconds since the epoch
    zone: tzinfo | None  # the time zone of the thread's name and the markers; None: the host's
    upload_limit: int  # the guild's upload limit in bytes; larger files are linked


def thread_name(channel: str, now: float, zone: tzinfo | None) -> str:
    """The archive thread's name: the channel's name and the time the archive started."""
    raise NotImplementedError


def webhook_name(milliseconds: int, counter: int) -> str:
    """The archive webhook's name, from the time in milliseconds and a nanosecond counter."""
    raise NotImplementedError


def forwarded_name(author: Author) -> str:
    """The name that a message is forwarded under, one that Discord takes for a webhook."""
    raise NotImplementedError


async def archive(source: History, target: ArchiveTarget, options: Options) -> ArchiveThread:
    """Copy ``source``'s messages into a new public thread of ``target``; return the thread."""
    raise NotImplementedError
