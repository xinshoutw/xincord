"""Reviewers' cross mark: a post's messages are remembered, then redone with a review.

The owner's request of 2026-10-12; v3 had no such feature.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast, override

import discord
import pytest

from discord_fakes import FakeChannel, FakeMessage, forbidden
from plugin_fakes import FIXTURES
from xincord.plugins.ntust_announcements.config import Board, bundled_review_prompt
from xincord.plugins.ntust_announcements.messages import content_messages
from xincord.plugins.ntust_announcements.pages import Link, article_html
from xincord.plugins.ntust_announcements.store import Announcement, Announcements, Posted
from xincord.plugins.ntust_announcements.watch import Watcher
from xincord.plugins.ntust_announcements.web import FetchError, Page

if TYPE_CHECKING:
    from conftest import Scene
    from xincord.core.storage import Store

PAGES = FIXTURES / "plugins" / "ntust_announcements"
BOARD = "STUDENT_DORMITORY"
BOARD_URL = "https://student.ntust.edu.tw/p/403-1053-1436-1.php"
CHANNEL = 101
DORMITORY = Board.model_validate(
    {"name": BOARD, "url": BOARD_URL, "layout": "student-affairs", "channel-id": CHANNEL}
)
ARTICLE_URL = "https://student.ntust.edu.tw/p/406-1053-152183,r1436.php?Lang=zh-tw"
LINK = Link(BOARD, ARTICLE_URL, "Dorm notice")
ARTICLE_PAGE = (PAGES / "student-article.html").read_text(encoding="utf-8")
LONG = "a" * 1500 + "\n\n" + "b" * 1500  # two messages
REVIEWED = "# Reviewed"
LOGGER = "xincord.plugins.ntust_announcements"
CROSS_MARK = "\N{CROSS MARK}"
THUMBS_UP = "\N{THUMBS UP SIGN}"
REVIEWER = 7
# The dormitory's board alone, reviewed by user 7 with a prompt that shows what it got.
REVIEWING = f"""\
fetch-interval: 3600
api-keys: ["key-one"]
prompt: "{{{{page_url}}}} {{{{base_url}}}} {{{{now}}}} {{{{html}}}}"
reviewers: [{REVIEWER}]
review-prompt: "review {{{{markdown}}}} of {{{{html}}}}"
boards:
  - name: {BOARD}
    url: "{BOARD_URL}"
    layout: student-affairs
    channel-id: {CHANNEL}
"""
WITHOUT_REVIEW_PROMPT = REVIEWING.replace('review-prompt: "review {{markdown}} of {{html}}"\n', "")


def table(links: list[Link]) -> str:
    """A Student Affairs page that lists ``links``."""
    rows = "".join(
        f'<tr><td><a href="{link.url}">{link.title}</a></td><td>2026-10-11</td></tr>'
        for link in links
    )
    return f'<table class="listTB table"><tbody>{rows}</tbody></table>'


def warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The plugin's warnings."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == logging.WARNING
    ]


@dataclass
class Stage:
    """The board's watcher with fake pages, model, review and channel, and the real store."""

    store: Store
    pages: dict[str, Page | Exception] = field(default_factory=dict[str, Page | Exception])
    answer: str | None = LONG
    reviewed: str | None = REVIEWED
    refusals: list[Exception] = field(default_factory=list[Exception])
    sent: list[tuple[int, int, str]] = field(default_factory=list[tuple[int, int, str]])
    deleted: list[tuple[int, int]] = field(default_factory=list[tuple[int, int]])
    reviews: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    next_id: int = 900

    def __post_init__(self) -> None:
        self.pages[BOARD_URL] = Page(BOARD_URL, table([LINK]))
        self.pages[ARTICLE_URL] = Page(ARTICLE_URL, ARTICLE_PAGE)
        self.announcements = Announcements(self.store)
        self.watcher = Watcher(
            DORMITORY,
            self.page,
            self.convert,
            self.post,
            Posted(self.store),
            review=self.review,
            delete=self.delete,
            announcements=self.announcements,
        )

    async def page(self, url: str) -> Page:
        answer = self.pages.get(url, FetchError(404))
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def convert(self, html: str, link: Link) -> str | None:
        del html, link
        return self.answer

    async def review(self, html: str, link: Link, markdown: str) -> str | None:
        del link
        self.reviews.append((html, markdown))
        return self.reviewed

    async def post(self, channel: int, content: str) -> int:
        if self.refusals:
            raise self.refusals.pop(0)
        self.next_id += 1
        self.sent.append((channel, self.next_id, content))
        return self.next_id

    async def delete(self, channel: int, message_id: int) -> None:
        self.deleted.append((channel, message_id))


@pytest.fixture
def stage(store: Store) -> Stage:
    return Stage(store)


OLD = Announcement(LINK, CHANNEL, (11, 12))


@pytest.mark.xfail(strict=True, reason="Posted messages are remembered")
async def test_two_messages(stage: Stage) -> None:
    """Requirement: Posted messages are remembered."""
    await stage.watcher.check()

    ids = tuple(message_id for _, message_id, _ in stage.sent)
    announcement = Announcement(LINK, CHANNEL, ids)
    assert len(ids) == 2
    assert await stage.announcements.find(ids[0]) == announcement
    assert await stage.announcements.find(ids[1]) == announcement


@pytest.mark.xfail(strict=True, reason="A reviewer's cross mark redoes a post")
async def test_redo(stage: Stage) -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    await stage.announcements.save(OLD)

    await stage.watcher.redo(OLD)

    [(channel, new_id, content)] = stage.sent
    assert (channel, content) == (CHANNEL, content_messages(REVIEWED)[0])
    assert stage.reviews == [(article_html(ARTICLE_PAGE), LONG)]
    assert stage.deleted == [(CHANNEL, 11), (CHANNEL, 12)]
    assert await stage.announcements.find(11) is None
    assert await stage.announcements.find(12) is None
    assert await stage.announcements.find(new_id) == Announcement(LINK, CHANNEL, (new_id,))


@pytest.mark.xfail(strict=True, reason="A reviewer's cross mark redoes a post")
@pytest.mark.parametrize("failure", ["page", "post"])
async def test_old_post_stays(stage: Stage, failure: str, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    await stage.announcements.save(OLD)
    if failure == "page":
        stage.pages[ARTICLE_URL] = FetchError(503)
    else:
        stage.refusals.append(forbidden())

    await stage.watcher.redo(OLD)

    assert stage.deleted == []
    assert await stage.announcements.find(11) == OLD
    assert any(ARTICLE_URL in line and "old post stays" in line for line in warnings(caplog))


@pytest.mark.xfail(strict=True, reason="A reviewer's cross mark redoes a post")
async def test_review_fails(stage: Stage, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    await stage.announcements.save(OLD)
    stage.reviewed = None

    await stage.watcher.redo(OLD)

    assert [content for _, _, content in stage.sent] == content_messages(LONG)
    assert stage.deleted == [(CHANNEL, 11), (CHANNEL, 12)]
    assert any(ARTICLE_URL in line and "review" in line for line in warnings(caplog))


@dataclass
class Deleting(FakeMessage):
    """A message whose deletion is recorded by its ID."""

    record: list[int] = field(default_factory=list[int])

    @override
    async def delete(self) -> None:
        self.record.append(self.id)


@dataclass
class Channel(FakeChannel):
    """A channel that records which of its messages are deleted."""

    deleted: list[int] = field(default_factory=list[int])

    @override
    def get_partial_message(self, message_id: int, /) -> FakeMessage:
        return Deleting(sent=self.sent, id=message_id, channel_id=self.id, record=self.deleted)


def reaction(
    message_id: int, user_id: int, emoji: str = CROSS_MARK
) -> discord.RawReactionActionEvent:
    """The gateway's reaction of ``user_id`` with ``emoji`` to a message of the board's channel."""
    data = {
        "message_id": str(message_id),
        "channel_id": str(CHANNEL),
        "user_id": str(user_id),
        "guild_id": "1",
        "type": 0,
        "burst": False,
    }
    return discord.RawReactionActionEvent(
        cast("Any", data), discord.PartialEmoji(name=emoji), "REACTION_ADD"
    )


async def posted(scene: Scene) -> tuple[Channel, int]:
    """Let the board pass once; its channel and the ID of the first article's message."""
    channel = Channel(sent=[], id=CHANNEL)
    scene.channels[CHANNEL] = channel
    scene.ready.set()
    await scene.clock.asleep(1)  # the board passed once and waits
    contents = [str(fields["content"]) for _, fields in channel.sent]
    article = next(
        number for number, content in enumerate(contents) if content.endswith("Markdown")
    )
    return channel, 500 + article  # FakeChannel numbers its messages from 500


@pytest.mark.xfail(strict=True, reason="A reviewer's cross mark redoes a post")
@pytest.mark.parametrize("config", [REVIEWING])
async def test_cross_mark(scene: Scene) -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    channel, message_id = await posted(scene)
    fetched, posts = len(scene.web.fetched), len(scene.posts(CHANNEL))

    await scene.cog.on_raw_reaction_add(reaction(message_id, REVIEWER))
    await asyncio.gather(*scene.cog.redos)

    [article] = scene.web.fetched[fetched:]
    assert "/p/406-" in article
    assert scene.web.prompts[-1].startswith("review Markdown of ")
    assert len(scene.posts(CHANNEL)) == posts + 1
    assert channel.deleted == [message_id]


@pytest.mark.xfail(strict=True, reason="A reviewer's cross mark redoes a post")
@pytest.mark.parametrize("config", [REVIEWING])
async def test_ignored_reactions(scene: Scene) -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    channel, message_id = await posted(scene)
    fetched = len(scene.web.fetched)

    await scene.cog.on_raw_reaction_add(reaction(message_id, REVIEWER + 1))
    await scene.cog.on_raw_reaction_add(reaction(message_id, REVIEWER, THUMBS_UP))
    await scene.cog.on_raw_reaction_add(reaction(999, REVIEWER))

    assert scene.cog.redos == set()
    assert len(scene.web.fetched) == fetched
    assert channel.deleted == []


@pytest.mark.xfail(strict=True, reason="A reviewer's cross mark redoes a post")
@pytest.mark.parametrize("config", [REVIEWING])
async def test_one_redo_at_a_time(scene: Scene) -> None:
    """Requirement: A reviewer's cross mark redoes a post."""
    channel, message_id = await posted(scene)
    fetched = len(scene.web.fetched)
    scene.web.hold = asyncio.Event()  # the redo's page waits

    await scene.cog.on_raw_reaction_add(reaction(message_id, REVIEWER))
    await scene.cog.on_raw_reaction_add(reaction(message_id, REVIEWER))
    redos = len(scene.cog.redos)
    scene.web.hold.set()
    await asyncio.gather(*scene.cog.redos)

    assert redos == 1
    assert len(scene.web.fetched) == fetched + 1
    assert channel.deleted == [message_id]


@pytest.mark.xfail(strict=True, reason="The review prompt")
@pytest.mark.parametrize("config", [WITHOUT_REVIEW_PROMPT])
async def test_missing_key(scene: Scene) -> None:
    """Requirement: The review prompt."""
    _, message_id = await posted(scene)

    await scene.cog.on_raw_reaction_add(reaction(message_id, REVIEWER))
    await asyncio.gather(*scene.cog.redos)

    assert scene.web.prompts[-1].startswith(bundled_review_prompt().split("{{", 1)[0])
