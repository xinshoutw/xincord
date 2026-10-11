"""One board's passes: what they post, what the board remembers and what they log.

The board is the dormitory board on a trimmed copy of its page; every NTUST article serves a
trimmed copy of a student article, and Gemini, the channel and the clock are fakes.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:155-256
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementCacheManager.kt:181-235
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:61-102
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:185-237
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp
import pytest

from discord_fakes import forbidden
from plugin_fakes import FIXTURES, golden
from xincord.plugins.ntust_announcements.config import Board
from xincord.plugins.ntust_announcements.messages import content_messages, link_message
from xincord.plugins.ntust_announcements.pages import Link, article_html, is_article
from xincord.plugins.ntust_announcements.store import NAMESPACE, Posted, posted_document
from xincord.plugins.ntust_announcements.watch import Watcher
from xincord.plugins.ntust_announcements.web import FetchError, Page

if TYPE_CHECKING:
    from xincord.core.storage import Store

PAGES = FIXTURES / "plugins" / "ntust_announcements"
BOARD = "STUDENT_DORMITORY"
BOARD_URL = "https://student.ntust.edu.tw/p/403-1053-1436-1.php"
CHANNEL = 101
DORMITORY = Board.model_validate(
    {"name": BOARD, "url": BOARD_URL, "layout": "student-affairs", "channel-id": CHANNEL}
)
ENTRIES = [
    Link(item["type"], item["url"], item["title"])
    for item in golden("ntust_announcements")["entries"]["student-dormitory.html"]
]
ARTICLES = [link for link in ENTRIES if is_article(link.url)]  # all but the Google Docs entry
BOARD_PAGE = (PAGES / "student-dormitory.html").read_text(encoding="utf-8")
ARTICLE_PAGE = (PAGES / "student-article.html").read_text(encoding="utf-8")
LOGGER = "xincord.plugins.ntust_announcements"


def table(links: list[Link]) -> str:
    """A Student Affairs page that lists ``links``."""
    rows = "".join(
        f'<tr><td><a href="{link.url}">{link.title}</a></td><td>2026-10-11</td></tr>'
        for link in links
    )
    return f'<table class="listTB table"><tbody>{rows}</tbody></table>'


def markdown(link: Link) -> str:
    """What the fake Gemini answers for an article."""
    return f"Markdown of {link.url}"


def expected_posts(links: list[Link]) -> list[tuple[int, str]]:
    """The messages that post ``links``: articles as their Markdown, others as title links."""
    return [
        (CHANNEL, message)
        for link in links
        for message in (
            content_messages(markdown(link))
            if is_article(link.url)
            else [link_message(link.title, link.url)]
        )
    ]


@dataclass
class Scene:
    """The board's watcher with fake pages, Gemini and channel, and the real store."""

    posted: Posted
    pages: dict[str, Page | Exception] = field(default_factory=dict[str, Page | Exception])
    answers: dict[str, str | None] = field(default_factory=dict[str, str | None])
    refusals: list[Exception | None] = field(default_factory=list[Exception | None])
    sent: list[tuple[int, str]] = field(default_factory=list[tuple[int, str]])
    fetched: list[str] = field(default_factory=list[str])
    converted: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    stored_when_converting: list[list[str]] = field(default_factory=list[list[str]])

    def __post_init__(self) -> None:
        self.pages[BOARD_URL] = Page(BOARD_URL, BOARD_PAGE)
        for link in ARTICLES:
            self.pages[link.url] = Page(link.url, ARTICLE_PAGE)
        self.watcher = Watcher(DORMITORY, self.page, self.convert, self.post, self.posted)

    async def page(self, url: str) -> Page:
        self.fetched.append(url)
        answer = self.pages.get(url, FetchError(404))
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def convert(self, html: str, link: Link) -> str | None:
        self.converted.append((html, link.url))
        self.stored_when_converting.append([entry.url for entry in await self.posted.load(BOARD)])
        return self.answers.get(link.url, markdown(link))

    async def post(self, channel: int, content: str) -> None:
        if self.refusals and (error := self.refusals.pop(0)) is not None:
            raise error
        self.sent.append((channel, content))

    async def stored(self) -> tuple[Link, ...]:
        return await self.posted.load(BOARD)


@pytest.fixture
def scene(store: Store) -> Scene:
    return Scene(Posted(store))


def plugin_lines(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """The plugin's log lines at ``level``."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == level
    ]


async def test_first_pass(scene: Scene) -> None:
    """Requirement: New announcements are posted in board order."""
    await scene.watcher.check()

    # v3's first run: every entry, in page order; the Google Docs entry as its title link.
    assert scene.sent == expected_posts(ENTRIES)
    assert scene.fetched == [BOARD_URL, *(link.url for link in ARTICLES)]
    assert scene.converted == [(article_html(ARTICLE_PAGE), link.url) for link in ARTICLES]
    assert await scene.stored() == tuple(ENTRIES)


async def test_posted_links(scene: Scene) -> None:
    """Requirement: New announcements are posted in board order."""
    await scene.posted.save(BOARD, ENTRIES[:3])

    await scene.watcher.check()

    assert scene.sent == expected_posts(ENTRIES[3:])
    assert await scene.stored() == tuple(ENTRIES)


async def test_duplicates_and_blank_entries(scene: Scene) -> None:
    """Requirement: New announcements are posted in board order."""
    first, second = ARTICLES[:2]
    blank = Link(BOARD, ARTICLES[2].url, " ")
    scene.pages[BOARD_URL] = Page(BOARD_URL, table([first, first, blank, second]))

    await scene.watcher.check()

    assert scene.sent == expected_posts([first, second])
    assert await scene.stored() == (first, second)


async def test_content_that_cannot_be_converted(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: New announcements are posted in board order."""
    no_container, not_converted = ARTICLES[:2]
    scene.pages[no_container.url] = Page(no_container.url, "<p>No container</p>")
    scene.answers[not_converted.url] = None  # Gemini failed every attempt

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        await scene.watcher.check()

    assert scene.sent[:2] == [
        (CHANNEL, link_message(no_container.title, no_container.url)),
        (CHANNEL, link_message(not_converted.title, not_converted.url)),
    ]
    assert await scene.stored() == tuple(ENTRIES)
    warnings = plugin_lines(caplog, logging.WARNING)
    assert len(warnings) == 2
    assert all(f"board {BOARD}" in line for line in warnings)
    assert no_container.url in warnings[0]
    assert not_converted.url in warnings[1]


async def test_stored_once_posted(scene: Scene, store: Store) -> None:
    """Requirement: Each board remembers what it posted."""
    await scene.watcher.check()

    # When the second article was converted, the first was stored, in page order.
    assert scene.stored_when_converting[:3] == [
        [],
        [ARTICLES[0].url],
        [ARTICLES[0].url, ARTICLES[1].url],
    ]
    assert await store.get(NAMESPACE, BOARD) == posted_document(ENTRIES)


async def test_retried(scene: Scene) -> None:
    """Requirement: Each board remembers what it posted."""
    failed_page, refused = ARTICLES[1], ARTICLES[2]
    scene.pages[failed_page.url] = FetchError(500)
    scene.refusals = [None, forbidden()]  # the first post works, the second is refused

    await scene.watcher.check()

    others = [link for link in ENTRIES if link not in {failed_page, refused}]
    assert scene.sent == expected_posts(others)
    assert await scene.stored() == tuple(others)

    scene.pages[failed_page.url] = Page(failed_page.url, ARTICLE_PAGE)
    scene.sent.clear()
    await scene.watcher.check()

    # v3 never retried: its list held them once the cycle ended.
    assert scene.sent == expected_posts([failed_page, refused])
    assert await scene.stored() == tuple(ENTRIES)


async def test_links_that_leave_the_page(scene: Scene) -> None:
    """Requirement: Each board remembers what it posted."""
    await scene.watcher.check()
    scene.sent.clear()

    scene.pages[BOARD_URL] = Page(BOARD_URL, table(ENTRIES[2:]))  # a partial page
    await scene.watcher.check()
    assert await scene.stored() == (*ENTRIES[2:], *ENTRIES[:2])

    scene.pages[BOARD_URL] = Page(BOARD_URL, BOARD_PAGE)  # the whole page again
    await scene.watcher.check()

    # v3 dropped them from its list and posted them again.
    assert scene.sent == []
    assert await scene.stored() == tuple(ENTRIES)


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(FetchError(404), id="404"),
        pytest.param(aiohttp.ClientConnectionError("Cannot connect"), id="no connection"),
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(Page(BOARD_URL, "<p>Maintenance</p>"), id="no entries"),
        pytest.param(Page(BOARD_URL, table([Link(BOARD, " ", "No link")])), id="blank link"),
    ],
)
async def test_failed_board_page(scene: Scene, store: Store, answer: Page | Exception) -> None:
    """Requirement: Each board remembers what it posted."""
    await scene.posted.save(BOARD, ENTRIES[:1])
    scene.pages[BOARD_URL] = answer

    await scene.watcher.check()

    assert scene.sent == []
    assert await store.get(NAMESPACE, BOARD) == posted_document(ENTRIES[:1])


async def test_broken_document(
    scene: Scene, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Each board remembers what it posted."""
    await store.put(NAMESPACE, BOARD, {"items": "broken"})

    await scene.watcher.check()

    # v3 dropped broken items, and their links counted as new.
    assert scene.sent == []
    assert scene.converted == []
    assert await store.get(NAMESPACE, BOARD) == {"items": "broken"}
    [error] = plugin_lines(caplog, logging.ERROR)
    assert f"board {BOARD}" in error


async def test_part_refused(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Each board remembers what it posted."""
    long = ARTICLES[0]
    scene.answers[long.url] = "a" * 1500 + "\n" + "b" * 1500  # two messages
    scene.refusals = [None, forbidden()]

    await scene.watcher.check()

    # Posting it again would repeat its start: it counts as posted, with an error.
    assert scene.sent[0] == (CHANNEL, content_messages(scene.answers[long.url] or "")[0])
    assert (await scene.stored())[0] == long
    [error] = plugin_lines(caplog, logging.ERROR)
    assert "part 2 of 2" in error
    assert long.url in error


async def test_repeated_failure(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    scene.pages[BOARD_URL] = FetchError(503)

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        for _ in range(3):
            await scene.watcher.check()

    [warning] = plugin_lines(caplog, logging.WARNING)
    assert f"NtustAnnouncements board {BOARD}" in warning
    assert "code 503" in warning
    assert len([line for line in plugin_lines(caplog, logging.DEBUG) if "code 503" in line]) == 2


async def test_recovery(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    scene.pages[BOARD_URL] = FetchError(503)
    for _ in range(3):
        await scene.watcher.check()
    scene.pages[BOARD_URL] = Page(BOARD_URL, BOARD_PAGE)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        for _ in range(3):
            await scene.watcher.check()

    works = [line for line in plugin_lines(caplog, logging.INFO) if "works again" in line]
    assert works == [
        f"NtustAnnouncements board {BOARD}: its page works again after 3 failed passes"
    ]


async def test_refused_posts_logged(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    scene.refusals = [forbidden()] * (2 * len(ENTRIES))

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        await scene.watcher.check()
        await scene.watcher.check()

    [warning] = plugin_lines(caplog, logging.WARNING)
    assert f"board {BOARD}: channel {CHANNEL} refused" in warning
    assert "403 Forbidden" in warning
    assert scene.sent == []
    assert await scene.stored() == ()


async def test_article_network_error(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Each board remembers what it posted."""
    unreachable = ARTICLES[0]
    scene.pages[unreachable.url] = aiohttp.ClientConnectionError("Connection reset")

    with caplog.at_level(logging.INFO, logger=LOGGER):
        await scene.watcher.check()
        assert unreachable not in await scene.stored()
        scene.pages[unreachable.url] = Page(unreachable.url, ARTICLE_PAGE)
        scene.sent.clear()
        await scene.watcher.check()

    assert scene.sent == expected_posts([unreachable])
    [error] = plugin_lines(caplog, logging.ERROR)
    assert f"the article {unreachable.url} failed: Connection reset" in error
    assert f"NtustAnnouncements board {BOARD}: its articles load again after 1 failures" in (
        plugin_lines(caplog, logging.INFO)
    )


async def test_document_fixed(scene: Scene, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Each board remembers what it posted."""
    await store.put(NAMESPACE, BOARD, {"items": "broken"})
    await scene.watcher.check()
    await store.delete(NAMESPACE, BOARD)  # the operator deletes it

    with caplog.at_level(logging.INFO, logger=LOGGER):
        for _ in range(3):  # an episode ends after three successes in a row
            await scene.watcher.check()

    assert scene.sent == expected_posts(ENTRIES)
    assert f"NtustAnnouncements board {BOARD}: its posted list reads again" in plugin_lines(
        caplog, logging.INFO
    )


async def test_unexpected_error(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    scene.pages[BOARD_URL] = RuntimeError("unexpected")

    await scene.watcher.check()  # logs and returns: the next pass comes as usual

    [record] = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert record.getMessage() == f"NtustAnnouncements board {BOARD}: the pass failed"
    assert record.exc_info is not None


async def test_refused_posts(scene: Scene) -> None:
    """Requirement: Each board remembers what it posted."""
    scene.refusals = [forbidden()] * (3 * len(ENTRIES))  # a wrong channel or a missing permission
    for _ in range(3):
        await scene.watcher.check()

    # Each article was fetched and converted once: Gemini's quota is not spent at every pass.
    assert scene.converted == [(article_html(ARTICLE_PAGE), link.url) for link in ARTICLES]
    assert scene.fetched.count(ARTICLES[0].url) == 1

    scene.refusals.clear()
    await scene.watcher.check()

    assert scene.sent == expected_posts(ENTRIES)
    assert len(scene.converted) == len(ARTICLES)


async def test_announcement_that_raises(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding or showing the keys."""
    failing = ARTICLES[0]
    scene.pages[failing.url] = RuntimeError("unexpected")

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        await scene.watcher.check()
        await scene.watcher.check()

    # The board's other entries are posted; the failing one is tried again at each pass.
    assert scene.sent == expected_posts([link for link in ENTRIES if link != failing])
    assert scene.fetched.count(failing.url) == 2
    [error] = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert failing.url in error.getMessage()
    assert error.exc_info is not None

    scene.pages[failing.url] = Page(failing.url, ARTICLE_PAGE)
    with caplog.at_level(logging.INFO, logger=LOGGER):
        for _ in range(3):
            await scene.watcher.check()

    assert scene.sent[-1] == expected_posts([failing])[-1]
    assert (
        f"NtustAnnouncements board {BOARD}: its announcements work again after 2 failures"
        in plugin_lines(caplog, logging.INFO)
    )


async def test_store_write_fails(scene: Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Each board remembers what it posted."""

    async def locked(_posted: Posted, _board: str, _links: object) -> None:
        msg = "database is locked"
        raise sqlite3.OperationalError(msg)

    with monkeypatch.context() as patched:
        patched.setattr(Posted, "save", locked)
        # Each pass posts one announcement, then fails to store it and ends.
        for _ in range(len(ENTRIES)):
            await scene.watcher.check()

    assert scene.sent == expected_posts(ENTRIES)  # none posted twice
    await scene.watcher.check()  # the store works again
    assert await scene.stored() == tuple(ENTRIES)
    assert scene.sent == expected_posts(ENTRIES)
