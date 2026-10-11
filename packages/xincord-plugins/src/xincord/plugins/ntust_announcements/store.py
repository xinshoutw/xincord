"""Each board's posted links, in the store as v3's document.

v3 kept them in MongoDB (database ``NtustManager``, collection ``current_announcement_lists``,
``_id`` = the board's name), the value being Core's ``TypedListWrapper``: ``{"items": [{"type",
"url", "title"}], "itemTypeName": ...}``. The store keeps that value under the board's name, so the
planned v3 data import copies it unchanged. Each board has one writer, its own loop.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementCacheManager.kt:10-224
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from .pages import Link

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from xincord.core.storage import JSON, Store

NAMESPACE = "NtustAnnouncements"
POSTS = f"{NAMESPACE}.posts"  # each posted message's announcement, by message ID
KEEP = 100  # links that left a board's page and are still remembered
FIELDS = ("type", "url", "title")  # an item's fields, in Moshi's order


class DataError(Exception):
    """A board's document is not v3's shape; it is left as it is."""


def parse_posted(document: JSON) -> tuple[Link, ...]:
    """The links of a board's document, in its order.

    v3's ``itemTypeName`` is ignored. v3 dropped broken items one by one, after which their links
    counted as new and were posted again; a broken document raises instead.

    Raises:
        DataError: The document is not an object whose ``items`` are objects with text fields
            ``type``, ``url`` and ``title``.
    """
    items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list):
        msg = "not v3's document: expected an object with a list of items"
        raise DataError(msg)
    links: list[Link] = []
    for item in items:
        fields = cast("dict[str, JSON]", item) if isinstance(item, dict) else {}
        board, url, title = (fields.get(name) for name in FIELDS)
        if not (isinstance(board, str) and isinstance(url, str) and isinstance(title, str)):
            msg = "not v3's document: an item lacks a text type, url or title"
            raise DataError(msg)
        links.append(Link(board, url, title))
    return tuple(links)


def posted_document(links: Sequence[Link]) -> dict[str, JSON]:
    """The document of a board's posted links, in v3's shape (Moshi left out a null type name)."""
    items: list[JSON] = [
        {"type": link.board, "url": link.url, "title": link.title} for link in links
    ]
    return {"items": items}


def remember(
    stored: Sequence[Link], page: Sequence[Link], posted: Collection[str]
) -> tuple[Link, ...]:
    """The links a board keeps after a post: the page's posted links, then those that left it.

    ``posted`` holds the URLs posted so far, the stored ones included. The page's links among them
    come first, in page order, once each and with the page's titles; then the stored links that
    are no longer on the page, in their order (the most recent first), at most ``KEEP``. v3 kept
    the page's links only, so a link that left the page and came back was posted again; a link
    that failed is not kept, so the next pass posts it.
    """
    kept: dict[str, Link] = {}
    for link in page:
        if link.url in posted:
            kept.setdefault(link.url, link)
    on_page = {link.url for link in page}
    left: dict[str, Link] = {}
    for link in stored:
        if link.url not in on_page:
            left.setdefault(link.url, link)
    return (*kept.values(), *list(left.values())[:KEEP])


@dataclass(frozen=True)
class Announcement:
    """An announcement's posted messages: what a reviewer's cross mark redoes."""

    link: Link
    channel_id: int
    message_ids: tuple[int, ...]  # in posting order


def announcement_document(announcement: Announcement) -> dict[str, JSON]:
    """The document stored under each of the announcement's message IDs."""
    link = announcement.link
    return {
        "type": link.board,
        "url": link.url,
        "title": link.title,
        "channel": announcement.channel_id,
        "messages": list(announcement.message_ids),
    }


def parse_announcement(document: JSON) -> Announcement | None:
    """The announcement of a stored document, or None when it is missing or not that shape."""
    fields = cast("dict[str, JSON]", document) if isinstance(document, dict) else {}
    board, url, title = (fields.get(name) for name in FIELDS)
    channel, messages = fields.get("channel"), fields.get("messages")
    if not (
        isinstance(board, str)
        and isinstance(url, str)
        and isinstance(title, str)
        and isinstance(channel, int)
        and isinstance(messages, list)
    ):
        return None
    ids = [message for message in messages if isinstance(message, int)]
    return Announcement(Link(board, url, title), channel, tuple(ids))


@dataclass(frozen=True)
class Announcements:
    """Each posted message's announcement, in the store under the message's ID.

    One entry per message, so that a cross mark on any part finds the whole post, also after a
    restart. Entries stay until a redo replaces them: a few a day.
    """

    store: Store

    async def save(self, announcement: Announcement) -> None:
        """Store the announcement under each of its message IDs."""
        document = announcement_document(announcement)
        for message_id in announcement.message_ids:
            await self.store.put(POSTS, str(message_id), document)

    async def find(self, message_id: int) -> Announcement | None:
        """The announcement that posted ``message_id``, or None."""
        return parse_announcement(await self.store.get(POSTS, str(message_id)))

    async def forget(self, announcement: Announcement) -> None:
        """Delete the entries of the announcement's message IDs."""
        for message_id in announcement.message_ids:
            await self.store.delete(POSTS, str(message_id))


@dataclass(frozen=True)
class Posted:
    """The boards' documents in the store."""

    store: Store

    async def load(self, board: str) -> tuple[Link, ...]:
        """The links that ``board`` posted; none when it has no document, as v3's first run.

        Raises:
            DataError: The board's document is not v3's shape.
        """
        document = await self.store.get(NAMESPACE, board)
        return () if document is None else parse_posted(document)

    async def save(self, board: str, links: Sequence[Link]) -> None:
        """Store the links that ``board`` keeps."""
        await self.store.put(NAMESPACE, board, posted_document(links))
