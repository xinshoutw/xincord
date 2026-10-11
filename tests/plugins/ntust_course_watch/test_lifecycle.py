"""The loop: from READY until the plugin unloads, one registered course per step."""

import asyncio
import importlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeMessage, Sent, forbidden, not_found
from plugin_fakes import golden, load_plugin, until
from xincord.plugins.ntust_course_watch.courses import Course
from xincord.plugins.ntust_course_watch.web import open_api

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from conftest import Scene
    from plugin_fakes import Ready
    from xincord.core.storage import Store
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch

GOLDEN = golden("ntust_course_watch")
NAME = GOLDEN["courses"]["CE162A001"]["name"]
SEATS = Course("CE162A001", NAME, 25, 60)
FULL = Course("CE162A001", NAME, 60, 60)


def mentions(*users: int) -> dict[str, object]:
    """``AllowedMentions.to_dict()`` for a post that may ping ``users`` only."""
    allowed = discord.AllowedMentions(
        everyone=False,
        users=[discord.Object(user) for user in users] if users else False,
        roles=False,
        replied_user=False,
    )
    return dict(allowed.to_dict())


@dataclass
class HeldChannel(FakeChannel):
    """A channel whose posts wait for ``gate``, as Discord's rate limit holds them."""

    gate: asyncio.Event = field(default_factory=asyncio.Event)

    async def send(self, **fields: object) -> FakeMessage:
        """Wait for the gate, then record the post."""
        await self.gate.wait()
        return await super().send(**fields)


@asynccontextmanager
async def opened(api: object) -> AsyncGenerator[object]:
    """Stands for ``open_api`` with ``api`` as its course query."""
    yield api


def allowed(fields: dict[str, object]) -> dict[str, object]:
    """The ``allowed_mentions`` of a post, as Discord gets them."""
    value = fields["allowed_mentions"]
    assert isinstance(value, discord.AllowedMentions)
    return dict(value.to_dict())


async def test_start_at_ready(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    await scene.ready.waiters(1)

    # Nothing before READY: --no-online never gets there.
    assert scene.api.asked == []
    assert scene.api.opened == 0

    scene.ready.set()
    await scene.steps(1)

    assert scene.api.asked == [("1151", "CE162A001")]  # at once
    assert scene.api.opened == 1


async def test_loaded_into_a_ready_bot(
    store: Store, tmp_path: Path, ready: Ready, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    # The module that the load's import finds, as the cog's default course query: discord.py
    # executes the plugin's package again but reuses its imported modules.
    module = importlib.import_module("xincord.plugins.ntust_course_watch.cog")
    asked: list[str] = []

    class Api:
        async def course(self, semester: str, code: str) -> Course | None:
            del semester
            asked.append(code)
            return None

    monkeypatch.setattr(module, "open_api", lambda: opened(Api()))
    ready.set()  # as after /xincord reload NtustCourseWatch
    await store.put("NtustCourseWatch", "user_record_map", {"CE162A001": {"5": ["1"]}})

    bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store)
    cog = cast("NtustCourseWatch", bot.get_cog("NtustCourseWatch"))
    assert cog.tasks
    await until(lambda: len(asked) >= 1)

    assert asked[0] == "CE162A001"


async def test_before_the_start(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    scene.clock.now = scene.cog.config.start - timedelta(seconds=2)
    scene.ready.set()

    await scene.steps(1)
    await scene.wake(2)

    # Nothing is asked before the start.
    assert scene.api.asked == []
    await scene.wake(3)  # the start has passed now
    assert scene.api.asked == [("1151", "CE162A001")]
    assert scene.clock.waits == [1.5, 1.5, 1.5]


async def test_nothing_registered(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    assert scene.cog.tasks
    scene.ready.set()

    await scene.steps(1)
    await scene.wake(2)
    assert scene.api.asked == []  # nothing is asked with nobody registered
    await scene.cog.registrations.add("CE162A002", 5, 1)
    await scene.wake(3)

    assert scene.api.asked == [("1151", "CE162A002")]


async def test_courses_in_turn(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A002", 5, 1)
    await scene.cog.registrations.add("CE162A001", 6, 2)
    scene.ready.set()

    await scene.steps(1)
    await scene.wake(2)
    await scene.wake(3)

    assert [code for _, code in scene.api.asked] == ["CE162A001", "CE162A002", "CE162A001"]
    assert scene.clock.waits == [1.5, 1.5, 1.5]  # the interval from one start to the next


async def test_slow_answers(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    scene.api.delay = 1.0
    scene.ready.set()

    await scene.steps(1)
    scene.api.delay = 2.0
    await scene.wake(2)

    assert scene.clock.waits == [0.5, 0.1]  # 100 ms at least after a slow answer


async def test_unload(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    [task] = scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    scene.ready.set()
    await scene.steps(1)

    await scene.bot.remove_cog("NtustCourseWatch")  # what an unload or a reload does
    await scene.clock.wake()
    await asyncio.sleep(0)

    assert task.done()
    assert scene.api.closed == 1  # the session closed with the loop
    assert len(scene.api.asked) == 1


async def test_unload_before_ready(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    [task] = scene.cog.tasks
    await scene.ready.waiters(1)

    await scene.bot.remove_cog("NtustCourseWatch")  # as --no-online's unload

    assert task.done()
    assert scene.api.opened == 0


async def test_unload_cancels_posts(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    scene.api.answers["CE162A001"] = [SEATS]
    scene.channels[5] = HeldChannel(sent=list[Sent](), id=5)
    scene.ready.set()
    await until(lambda: bool(scene.cog.posting))
    [post] = scene.cog.posting

    await scene.bot.remove_cog("NtustCourseWatch")

    assert post.cancelled()


async def test_reload(scene: Scene) -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    [old] = scene.cog.tasks
    await scene.ready.waiters(1)

    summary = await scene.bot.reload("NtustCourseWatch")  # the console's and /xincord's reload

    assert "NtustCourseWatch" in summary
    assert old.done()  # the old loop ends
    [new] = scene.cog.tasks  # the new version's
    assert not new.done()


async def test_tests_stay_offline() -> None:
    """Requirement: Registered courses are checked in turn from READY."""
    # The conftest's guard: a plugin that a test left with its real course query reaches no NTUST.
    async with open_api() as api:
        with pytest.raises(OSError, match="the tests do not reach the network"):
            await api.course("1151", "CE162A001")


async def test_alerts_through_partial_messageables(scene: Scene) -> None:
    """Requirement: Channels hear about courses with seats."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    await scene.cog.registrations.add("CE162A001", 5, 2)
    scene.api.answers["CE162A001"] = [SEATS, FULL]
    scene.ready.set()

    await scene.steps(1)
    await scene.wake(2)

    [available, full] = scene.posts(5)
    assert available["content"] == GOLDEN["alerts"]["available"]
    assert allowed(available) == mentions(1, 2)  # the registered members, nobody else
    assert full["content"] == GOLDEN["alerts"]["full"]
    assert allowed(full) == mentions()  # nobody


async def test_deleted_channel(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Failures are logged without flooding."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    await scene.cog.registrations.add("CE162A001", 6, 2)
    scene.api.answers["CE162A001"] = [SEATS]
    scene.channel(5).error = not_found("Unknown Channel")
    scene.ready.set()

    with caplog.at_level(logging.INFO):
        await scene.steps(1)

    # A deleted channel's registrations are forgotten.
    assert await scene.cog.registrations.load() == {"CE162A001": {6: (2,)}}
    assert "channel 5 is gone" in caplog.text
    assert len(scene.posts(6)) == 1


async def test_refused_posts(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Failures are logged without flooding."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    scene.api.answers["CE162A001"] = [SEATS]
    scene.channel(5).error = forbidden()
    scene.ready.set()

    with caplog.at_level(logging.WARNING):
        await scene.steps(1)
        scene.clock.advance(60)  # the alert comes again after alert-interval
        await scene.wake(2)

    refused = [record for record in caplog.records if "channel 5 refused" in record.message]
    assert len(refused) == 1  # once per episode
    assert "Missing Permissions" in refused[0].message
    assert await scene.cog.registrations.load() == {"CE162A001": {5: (1,)}}


async def test_posts_work_again(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Failures are logged without flooding."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    scene.api.answers["CE162A001"] = [SEATS]
    scene.channel(5).error = forbidden()
    scene.ready.set()
    await scene.steps(1)
    scene.channel(5).error = None  # the permission is back

    with caplog.at_level(logging.INFO):
        for steps in range(2, 5):
            scene.clock.advance(60)
            await scene.wake(steps)

    assert len(scene.posts(5)) == 3
    [again] = [record for record in caplog.records if "takes the alerts again" in record.message]
    assert "after 1 refusals" in again.message


async def test_deleted_channel_with_two_posts(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Failures are logged without flooding."""
    assert scene.cog.tasks
    members = [1_000_000_000_000_000_000 + number for number in range(120)]
    for member in members:  # their mentions need two posts
        await scene.cog.registrations.add("CE162A001", 5, member)
    scene.api.answers["CE162A001"] = [SEATS]
    scene.channel(5).error = not_found("Unknown Channel")
    scene.ready.set()

    with caplog.at_level(logging.INFO):
        await scene.steps(1)

    assert len([record for record in caplog.records if "is gone" in record.message]) == 1
    assert await scene.cog.registrations.load() == {}
    assert 5 not in scene.cog.posts  # the channel's failure record went with it


async def test_loop_ended_by_an_error(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Failures are logged without flooding."""
    [task] = scene.cog.tasks

    def missing() -> object:
        msg = "twca-secure-ssl-ca.pem"
        raise FileNotFoundError(msg)

    scene.cog.open_api = cast("Any", missing)
    scene.ready.set()
    await asyncio.wait({task}, timeout=5)
    await asyncio.sleep(0)  # the task's callbacks run

    # Nothing awaits the loop until the plugin unloads: its end must reach the log.
    [record] = [record for record in caplog.records if "the loop stopped" in record.message]
    assert record.exc_info is not None


async def test_unexpected_post_error(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Failures are logged without flooding."""
    assert scene.cog.tasks
    await scene.cog.registrations.add("CE162A001", 5, 1)
    scene.api.answers["CE162A001"] = [SEATS]
    scene.channel(5).error = RuntimeError("broken")
    scene.ready.set()

    await scene.steps(1)

    [record] = [record for record in caplog.records if "posting to channel 5" in record.message]
    assert record.exc_info is not None  # the traceback, since nothing awaits the post
    await scene.wake(2)  # the loop goes on
