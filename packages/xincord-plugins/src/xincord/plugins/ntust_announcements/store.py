"""Each board's posted links, in the store as v3's document.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementCacheManager.kt:10-224
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from xincord.core.storage import JSON, Store

    from .pages import Link

NAMESPACE = "NtustAnnouncements"
KEEP = 100  # links that left a board's page and are still remembered


class DataError(Exception):
    """A board's document is not v3's shape; it is left as it is."""


def parse_posted(document: JSON) -> tuple[Link, ...]:
    """The links of a board's document, in its order."""
    raise NotImplementedError


def posted_document(links: Sequence[Link]) -> dict[str, JSON]:
    """The document of a board's posted links, in v3's shape."""
    raise NotImplementedError


def remember(
    stored: Sequence[Link], page: Sequence[Link], posted: Collection[str]
) -> tuple[Link, ...]:
    """The links a board keeps after a post: the page's posted links, then those that left it."""
    raise NotImplementedError


@dataclass(frozen=True)
class Posted:
    """The boards' documents in the store."""

    store: Store

    async def load(self, board: str) -> tuple[Link, ...]:
        """The links that ``board`` posted, none when it has no document."""
        raise NotImplementedError

    async def save(self, board: str, links: Sequence[Link]) -> None:
        """Store the links that ``board`` keeps."""
        raise NotImplementedError
