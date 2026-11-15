"""The feed's passes: what waits, what is posted where, and what is remembered."""

import logging
import sqlite3
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from bulletin_fakes import DORMITORY, NOW, ORIGIN, WAIT, World, article_url, board
from discord_fakes import forbidden
from xincord.plugins.ntust_announcements.bulletin import AnswerError, FetchError
from xincord.plugins.ntust_announcements.messages import HEADER, link_message
from xincord.plugins.ntust_announcements.state import KEY, NAMESPACE, State, States, Waiting

if TYPE_CHECKING:
    from xincord.core.storage import Store

LOGGER = "xincord.plugins.ntust_announcements"
STUDENT_AFFAIRS = board("STUDENT_AFFAIRS", "1053", 102)
MAIN_OFFICE = board("STUDENT_MAIN_OFFICE", "1053-1435", 104, prefix="[Office]")
REWRITE = "### Who\n\n- Every resident"
DAY = timedelta(days=1)
LATER = timedelta(seconds=WAIT)
XFAIL = pytest.mark.xfail(strict=True, reason="read-bulletin-feed")


@pytest.fixture
async def world(store: Store) -> World:
    """The fakes over an empty store."""
    return World(store)


@pytest.fixture
async def started(world: World) -> World:
    """The fakes, the feed's position stored at the start of an empty feed."""
    await States(world.store).save(State(0))
    return world


def lines(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """The plugin's log lines at ``level``."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == level
    ]


def title_link(number: int, title: str = "Dormitory notice") -> list[str]:
    """The messages of an announcement posted as its title link."""
    return [link_message(title, article_url(number))]


@XFAIL
async def test_first_pass(world: World) -> None:
    """Requirement: The first read starts at the feed's end."""
    for number in range(1, 1201):
        world.api.publish(number, notify=number % 7 == 0, link_item=True)
    feed = world.feed()

    await feed.check()
    await feed.check()

    assert world.channels.sent == []
    assert world.api.reads == [0, 500, 1000, 1200]
    assert await world.states.load() == State(1200)


@XFAIL
async def test_several_reads(started: World) -> None:
    """Requirement: The first read starts at the feed's end."""
    world = started
    for number in range(1, 701):
        world.api.publish(number, notify=False, boards=("1017-631",))
    world.api.publish(701, link_item=True)  # event 701, read second
    world.api.publish(702)
    world.api.add("withdrawn", 702)  # after its publication: it never posts
    feed = world.feed()

    await feed.check()
    world.clock.value = NOW + LATER
    await feed.check()

    assert world.api.reads[:2] == [0, 500]
    assert world.channels.got(101) == title_link(701)


@XFAIL
async def test_rewrite_in_time(started: World) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    world = started
    world.api.publish(1)
    feed = world.feed()
    await feed.check()
    assert world.channels.sent == []

    world.clock.value = NOW + timedelta(minutes=10)
    world.api.render(1, REWRITE, at=world.clock.value)
    await feed.check()

    [content] = world.channels.got(101)
    assert content.startswith(f"{HEADER}\n# [Dormitory notice]({article_url(1)})\n\n")
    assert content.endswith(REWRITE)


@XFAIL
async def test_no_rewrite_in_time(started: World) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    world = started
    world.api.publish(1)
    feed = world.feed()
    world.clock.value = NOW + LATER - timedelta(seconds=1)
    await feed.check()
    assert world.channels.sent == []

    world.clock.value = NOW + LATER
    await feed.check()

    assert world.channels.got(101) == title_link(1)


@XFAIL
async def test_link_entry(started: World) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    world = started
    world.api.publish(1, link_item=True)

    await world.feed().check()

    assert world.channels.got(101) == title_link(1)


@XFAIL
@pytest.mark.parametrize("kind", ["published", "revised", "restored", "rendered", "unknown"])
async def test_not_notify_worthy(started: World, kind: str) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    world = started
    world.api.publish(1, notify=False, link_item=True)
    world.api.add(kind, 1)
    feed = world.feed()

    await feed.check()
    world.clock.value = NOW + DAY
    await feed.check()

    assert (world.channels.sent, world.api.asked) == ([], [])


@XFAIL
async def test_a_whole_site(started: World) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    world = started
    world.boards = (STUDENT_AFFAIRS,)
    world.api.publish(1, boards=("1053-1439",), link_item=True)

    await world.feed().check()

    assert world.channels.got(102) == title_link(1)


@XFAIL
async def test_other_boards_and_titles(started: World) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    world = started
    world.boards = (DORMITORY, MAIN_OFFICE)
    world.api.publish(1, boards=("1017-631",), link_item=True)
    world.api.publish(2, boards=("1053-1435",), title="Other news", link_item=True)
    world.api.publish(3, boards=("1053-1435",), title="[Office] News", link_item=True)

    await world.feed().check()

    assert world.channels.sent == [(104, title_link(3, "[Office] News")[0])]


@XFAIL
async def test_withdrawn(started: World) -> None:
    """Requirement: Notify-worthy announcements on a configured board wait for their rewrite."""
    world = started
    world.api.publish(1)
    feed = world.feed()
    await feed.check()

    world.api.add("withdrawn", 1)
    world.clock.value = NOW + LATER
    await feed.check()

    assert world.channels.sent == []


@XFAIL
async def test_two_boards_one_channel(started: World) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    world = started
    world.boards = (DORMITORY, board("STUDENT_AFFAIRS", "1053", 101))
    world.api.publish(1, link_item=True)

    await world.feed().check()

    assert world.channels.sent == [(101, title_link(1)[0])]


@XFAIL
async def test_two_channels(started: World) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    world = started
    world.boards = (STUDENT_AFFAIRS, DORMITORY)
    world.api.publish(1, link_item=True)

    await world.feed().check()

    assert [channel for channel, _ in world.channels.sent] == [102, 101]


@XFAIL
async def test_refused_post(started: World) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    world = started
    world.boards = (DORMITORY, STUDENT_AFFAIRS)
    world.channels.refusing[102] = forbidden()
    world.api.publish(1, link_item=True)
    feed = world.feed()

    await feed.check()
    await feed.check()
    del world.channels.refusing[102]
    await feed.check()
    await feed.check()

    assert world.channels.got(101) == title_link(1)
    assert world.channels.got(102) == title_link(1)


@XFAIL
async def test_refused_for_a_day(started: World, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    world = started
    world.channels.refusing[101] = forbidden()
    world.api.publish(1, link_item=True)
    feed = world.feed()
    await feed.check()
    world.clock.value = NOW + DAY - timedelta(seconds=1)
    await feed.check()
    assert (await world.states.load()) == State(1, (Waiting(1, NOW),))

    world.clock.value = NOW + DAY
    await feed.check()
    del world.channels.refusing[101]
    await feed.check()

    assert world.channels.sent == []
    [error] = lines(caplog, logging.ERROR)
    assert "announcement 1" in error
    assert "101" in error
    assert await world.states.load() == State(1)


@XFAIL
async def test_failed_read(started: World) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    world = started
    world.api.failing[1] = FetchError(503)
    world.api.publish(1, link_item=True)
    feed = world.feed()

    await feed.check()
    assert world.channels.sent == []
    del world.api.failing[1]
    await feed.check()

    assert world.api.asked == [1, 1]
    assert world.channels.got(101) == title_link(1)


@XFAIL
async def test_failed_reads_for_a_day(started: World, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    world = started
    world.api.failing[1] = OSError("connection reset")
    world.api.publish(1, link_item=True)
    feed = world.feed()
    await feed.check()

    world.clock.value = NOW + DAY
    await feed.check()

    [error] = lines(caplog, logging.ERROR)
    assert "announcement 1" in error
    assert await world.states.load() == State(1)


@XFAIL
async def test_gone(started: World, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Waiting announcements are posted to their boards' channels."""
    world = started
    world.api.publish(1, link_item=True)
    del world.api.announcements[1]
    feed = world.feed()

    await feed.check()
    await feed.check()

    assert world.api.asked == [1]
    assert any("announcement 1" in line for line in lines(caplog, logging.WARNING))
    assert world.channels.sent == []


@XFAIL
async def test_restart(started: World) -> None:
    """Requirement: The feed's position and the waiting announcements are stored."""
    world = started
    world.api.publish(1)
    await world.feed().check()
    world.api.publish(2, notify=False)

    restarted = world.feed()
    await restarted.check()
    assert world.api.reads[-1] == 1  # after the stored position
    world.clock.value = NOW + LATER
    await restarted.check()

    assert world.channels.got(101) == title_link(1)


@XFAIL
async def test_posted_channels(started: World) -> None:
    """Requirement: The feed's position and the waiting announcements are stored."""
    world = started
    world.boards = (DORMITORY, STUDENT_AFFAIRS)
    world.api.publish(1, link_item=True)
    await world.states.save(State(1, (Waiting(1, NOW, (101,)),)))

    await world.feed().check()

    assert [channel for channel, _ in world.channels.sent] == [102]
    assert await world.states.load() == State(1)


@XFAIL
async def test_broken_document(world: World, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The feed's position and the waiting announcements are stored."""
    world.api.publish(1, link_item=True)
    await world.store.put(NAMESPACE, KEY, {"after": "seven"})
    feed = world.feed()

    await feed.check()
    await feed.check()

    assert (world.api.reads, world.channels.sent) == ([], [])
    assert len(lines(caplog, logging.ERROR)) == 1
    assert await world.store.get(NAMESPACE, KEY) == {"after": "seven"}


@XFAIL
async def test_store_refusing_a_write(
    started: World, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The feed's position and the waiting announcements are stored."""
    world = started
    put = world.store.put
    refusing = True

    async def refused(namespace: str, key: str, value: object) -> None:
        if refusing:
            msg = "database is locked"
            raise sqlite3.OperationalError(msg)
        await put(namespace, key, value)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(world.store, "put", refused)
    world.api.publish(1, link_item=True)
    feed = world.feed()

    await feed.check()
    await feed.check()
    assert world.channels.got(101) == title_link(1)
    assert len(lines(caplog, logging.WARNING)) == 1
    refusing = False
    await feed.check()

    assert await world.states.load() == State(1)


@XFAIL
async def test_repeated_failure(started: World, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding."""
    world = started
    world.api.error = FetchError(503)
    feed = world.feed()

    for _ in range(3):
        await feed.check()

    [warning] = lines(caplog, logging.WARNING)
    assert ORIGIN in warning
    assert "code 503" in warning
    assert len(lines(caplog, logging.DEBUG)) == 2


@XFAIL
async def test_recovery(started: World, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding."""
    world = started
    world.api.error = FetchError(503)
    feed = world.feed()
    await feed.check()
    world.api.error = None

    for _ in range(3):
        await feed.check()

    [info] = [line for line in lines(caplog, logging.INFO) if "again" in line]
    assert "feed" in info


@XFAIL
async def test_unexpected_answer(started: World, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Problems are logged without flooding."""
    world = started
    world.api.publish(1, link_item=True)
    world.api.error = AnswerError("events: field required")

    await world.feed().check()

    [warning] = lines(caplog, logging.WARNING)
    assert "unexpected answer" in warning
    assert world.channels.sent == []
    assert await world.states.load() == State(0)
