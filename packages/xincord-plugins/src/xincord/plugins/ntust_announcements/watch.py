"""One board's passes: its new entries posted in page order, its posted list kept."""

import asyncio
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp
import discord

from xincord.plugins.failures import Failures

from .messages import content_messages, link_message
from .pages import article_html, board_links, is_article
from .store import Announcement, DataError, remember
from .strings import trim
from .web import FetchError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .config import Board
    from .pages import Link
    from .store import Announcements, Posted
    from .web import Page

type FetchPage = Callable[[str], Awaitable[Page]]
type Convert = Callable[[str, Link], Awaitable[str | None]]  # an article's HTML to Markdown
type Post = Callable[[int, str], Awaitable[int | None]]  # one message to a channel: its ID
# The model's check of a new conversion: (HTML, link, conversion) to the reviewed Markdown.
type Review = Callable[[str, Link, str], Awaitable[str | None]]
type Delete = Callable[[int, int], Awaitable[object]]  # one message of a channel
type Sleep = Callable[[float], Awaitable[object]]

logger = logging.getLogger(__name__)

# A page that did not arrive: aiohttp's errors and OSError, timeouts included.
NETWORK_ERRORS = (aiohttp.ClientError, OSError)
# A post that Discord refused or that did not reach it.
POST_ERRORS = (discord.HTTPException, aiohttp.ClientError, OSError)
EMPTY = "no entries"  # the kind of failure of a page that lists nothing


def _describe(error: BaseException) -> str:
    """The error's message, or its type when it has none (aiohttp's timeouts may have none)."""
    return str(error) or type(error).__name__


@dataclass
class Watcher:
    """One board and its effects: its pages, the model, its channel and its posted list."""

    board: Board
    page: FetchPage
    convert: Convert
    post: Post
    posted: Posted
    review: Review | None = None  # the second check of a redo; none: redone posts go unreviewed
    delete: Delete | None = None  # deletes a redone post's old messages
    announcements: Announcements | None = None  # the posted messages, for a reviewer's redo
    # Failure episodes: the board's page, its articles' pages, its posts and its document. Each
    # kind of failure is logged once per episode (v3 logged at every cycle).
    pages: Failures = field(default_factory=Failures)
    articles: Failures = field(default_factory=Failures)
    posts: Failures = field(default_factory=Failures)
    document: Failures = field(default_factory=Failures)
    errors: Failures = field(default_factory=Failures)  # announcements that raised unexpectedly
    # Links posted while the store refused to save them: posted, though not stored yet.
    delivered: set[str] = field(default_factory=set[str])
    # The messages of announcements that the channel refused, by URL, until they are posted or
    # leave the page.
    ready: dict[str, list[str]] = field(default_factory=dict[str, list[str]])

    @property
    def name(self) -> str:
        """How the logs name the board."""
        return f"NtustAnnouncements board {self.board.name}"

    async def run(self, interval: float, sleep: Sleep) -> None:
        """Pass at once, then ``interval`` seconds after each pass, until cancelled.

        v3 ran every board at a fixed rate from one scheduler; a board now waits for nothing but
        its own pass, so a long retry of the model holds up no other board.
        """
        while True:
            await self.check()
            await sleep(interval)

    async def redo(self, announcement: Announcement) -> bool:
        """Post ``announcement`` again, converted anew and reviewed, then delete its old messages.

        The new messages come first: when the article fails or the channel refuses them, the old
        post stays, also through a restart during the model's retries.

        Returns:
            Whether the new post replaced the old one.
        """
        link = announcement.link
        messages = await self._messages(link, review=True)
        if messages is None or not await self._post(link, messages):
            logger.warning("%s: %s was not posted again; its old post stays", self.name, link.url)
            return False
        for message_id in announcement.message_ids:
            await self._delete(announcement.channel_id, message_id)
        if self.announcements is not None:
            await self.announcements.forget(announcement)
        logger.info("%s: replaced the post of %s", self.name, link.url)
        return True

    async def _delete(self, channel: int, message_id: int) -> None:
        """Delete one old message; one that is gone already counts as deleted."""
        if self.delete is None:
            return
        try:
            await self.delete(channel, message_id)
        except discord.NotFound:
            pass
        except POST_ERRORS as error:
            logger.warning(
                "%s: channel %d kept message %d of a replaced post: %s",
                self.name,
                channel,
                message_id,
                _describe(error),
            )

    async def check(self) -> None:
        """One pass: post the page's entries that the board has not posted yet, in page order.

        Any unexpected error is logged with its traceback, and the next pass comes as usual;
        cancellation (an unload) ends the pass at once.
        """
        try:
            await self._pass()
        except Exception:
            logger.exception("%s: the pass failed", self.name)

    async def _pass(self) -> None:
        """v3's ``checkAnnouncementUpdates``, which remembers a link once it is posted."""
        links = await self._links()
        if links is None:
            return
        stored = await self._stored()
        if stored is None:
            return
        # The posts that the store has not taken yet count too, so that none is posted twice.
        posted = {link.url for link in stored} | self.delivered
        new: dict[str, Link] = {}
        for link in links:
            if link.url not in posted:
                new.setdefault(link.url, link)  # a link listed twice is posted once
        if new:
            logger.info("%s: %d new announcements", self.name, len(new))
        kept = stored
        clean = True  # no announcement raised in this pass
        for link in new.values():
            announced = await self._guarded(link)
            clean = clean and announced is not None
            if announced:
                posted.add(link.url)
                self.delivered.add(link.url)
                kept = remember(stored, links, posted)
                await self.posted.save(self.board.name, kept)
                self.delivered.clear()  # the document holds them now
        if clean and (failed := self.errors.succeed()):
            logger.info("%s: its announcements work again after %d failures", self.name, failed)
        if (tidied := remember(stored, links, posted)) != kept:
            await self.posted.save(self.board.name, tidied)  # new order, titles or links that left
            self.delivered.clear()
        on_page = {link.url for link in links}
        self.ready = {url: messages for url, messages in self.ready.items() if url in on_page}

    async def _links(self) -> list[Link] | None:
        """The page's entries with a title and a link, or None when the page failed (logged)."""
        try:
            page = await self.page(self.board.url)
        except FetchError as error:
            self._page_failed(error.status, logging.WARNING, f"answered with {error}")
            return None
        except NETWORK_ERRORS as error:
            self._page_failed(type(error), logging.ERROR, f"failed: {_describe(error)}")
            return None
        # Parsing takes about 0.3 s per MB: a worker thread keeps the event loop free.
        links = await asyncio.to_thread(board_links, page.text, self.board, page.url)
        valid = [link for link in links if trim(link.title) and trim(link.url)]
        if skipped := len(links) - len(valid):
            logger.debug("%s: skipped %d entries without a title or a link", self.name, skipped)
        if not valid:
            self._page_failed(EMPTY, logging.WARNING, "lists no entries")
            return None
        if failed := self.pages.succeed():
            logger.info("%s: its page works again after %d failed passes", self.name, failed)
        return valid

    def _page_failed(self, kind: object, level: int, detail: str) -> None:
        logger.log(
            level if self.pages.fail(kind) else logging.DEBUG,
            "%s: its page %s %s",
            self.name,
            self.board.url,
            detail,
        )

    async def _stored(self) -> tuple[Link, ...] | None:
        """The links that the board posted, or None when its document is broken (logged)."""
        try:
            stored = await self.posted.load(self.board.name)
        except DataError as error:
            logger.log(
                logging.ERROR if self.document.fail(DataError) else logging.DEBUG,
                "%s: its posted list is not v3's document, so the board posts nothing until "
                "the document is fixed or deleted: %s",
                self.name,
                error,
            )
            return None
        if self.document.succeed():
            logger.info("%s: its posted list reads again", self.name)
        return stored

    async def _guarded(self, link: Link) -> bool | None:
        """:meth:`_announce`, or None when it raised (logged with its traceback).

        One broken announcement holds up none of the board's later ones, as v3's guard around each
        did, and is tried again at the next pass.
        """
        try:
            return await self._announce(link)
        except Exception as error:
            logger.log(
                logging.ERROR if self.errors.fail(type(error)) else logging.DEBUG,
                "%s: announcing %s failed; it is tried again at the next pass",
                self.name,
                link.url,
                exc_info=error,
            )
            return None

    async def _announce(self, link: Link) -> bool:
        """Post one announcement; whether it counts as posted (v3's ``contentParser``).

        Messages that the channel refused wait in ``ready`` for the next pass, so that a refusing
        channel (a wrong ID, a missing permission) costs no attempt of the model at each pass.
        """
        messages = self.ready.get(link.url)
        if messages is None:
            messages = await self._messages(link)
            if messages is None:
                return False
        if await self._post(link, messages):
            self.ready.pop(link.url, None)
            return True
        self.ready[link.url] = messages
        return False

    async def _messages(self, link: Link, *, review: bool = False) -> list[str] | None:
        """An announcement's messages, or None when its article page failed (logged).

        An NTUST article goes through the model, and with ``review`` its conversion through the
        model's second check; any other link, or an article whose content cannot be converted, is
        its title link. An article page that fails is left for the next pass, which v3 never gave
        it.
        """
        if not is_article(link.url):
            return [link_message(link.title, link.url)]
        try:
            page = await self.page(link.url)
        except FetchError as error:
            self._article_failed(error.status, logging.WARNING, link, f"answered with {error}")
            return None
        except NETWORK_ERRORS as error:
            self._article_failed(type(error), logging.ERROR, link, f"failed: {_describe(error)}")
            return None
        if failed := self.articles.succeed():
            logger.info("%s: its articles load again after %d failures", self.name, failed)
        html = await asyncio.to_thread(article_html, page.text)
        if html is None:
            logger.warning(
                "%s: %s has no content to convert; posting its title", self.name, link.url
            )
            return [link_message(link.title, link.url)]
        content = await self.convert(html, link)
        if content is None:
            logger.warning(
                "%s: posting %s as its title, since the model could not convert it",
                self.name,
                link.url,
            )
            return [link_message(link.title, link.url)]
        if review and self.review is not None:
            reviewed = await self.review(html, link, content)
            if reviewed is None:
                logger.warning(
                    "%s: the review of %s failed; posting the new conversion as it is",
                    self.name,
                    link.url,
                )
            content = reviewed or content
        return content_messages(content)

    def _article_failed(self, kind: object, level: int, link: Link, detail: str) -> None:
        logger.log(
            level if self.articles.fail(kind) else logging.DEBUG,
            "%s: the article %s %s; it is tried again at the next pass",
            self.name,
            link.url,
            detail,
        )

    async def _post(self, link: Link, messages: list[str]) -> bool:
        """Send the messages in order; whether the announcement counts as posted.

        A refused first message posted nothing, and the announcement waits for the next pass. A
        refused later one leaves the start posted: posting it again would repeat it, so it counts
        as posted, with an error.
        """
        channel = self.board.channel_id
        posted: list[int] = []
        for number, message in enumerate(messages, start=1):
            try:
                message_id = await self.post(channel, message)
            except POST_ERRORS as error:
                if number > 1:
                    await self._remember(link, posted)
                    logger.error(  # noqa: TRY400 - Discord's answer, not a traceback, says why
                        "%s: channel %d refused part %d of %d of %s, so the rest is not posted: %s",
                        self.name,
                        channel,
                        number,
                        len(messages),
                        link.url,
                        _describe(error),
                    )
                    return True
                kind = error.status if isinstance(error, discord.HTTPException) else type(error)
                logger.log(
                    logging.WARNING if self.posts.fail(kind) else logging.DEBUG,
                    "%s: channel %d refused %s: %s",
                    self.name,
                    channel,
                    link.url,
                    _describe(error),
                )
                return False
            if message_id is not None:
                posted.append(message_id)
        await self._remember(link, posted)
        if failed := self.posts.succeed():
            logger.info(
                "%s: channel %d takes the posts again after %d refusals", self.name, channel, failed
            )
        logger.info("%s: posted %s", self.name, link.url)
        return True

    async def _remember(self, link: Link, posted: list[int]) -> None:
        """Store the posted messages for a reviewer's redo; a failure is a warning, no repost."""
        if self.announcements is None or not posted:
            return
        announcement = Announcement(link, self.board.channel_id, tuple(posted))
        try:
            await self.announcements.save(announcement)
        except sqlite3.Error as error:
            logger.warning(
                "%s: the messages of %s were not stored, so a cross mark on them does nothing: %s",
                self.name,
                link.url,
                error,
            )
