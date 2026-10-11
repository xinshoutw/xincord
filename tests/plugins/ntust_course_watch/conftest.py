"""Fixtures for the NtustCourseWatch tests: the plugin loads through its real entry point.

READY never comes unless a test sets it, so the plugin's loop waits for it; the loops left running
are cancelled when the test ends. No test reaches the network. ``scene`` loads the plugin with
semester 1151 and a start in the past, and replaces its course query, its channels, its waits and
its clocks.
"""

import asyncio
import errno
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import pytest

from discord_fakes import FakeChannel, Sent
from plugin_fakes import WAIT, Ready, load_plugin

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch
    from xincord.plugins.ntust_course_watch.courses import Course

PACKAGE = "xincord.plugins.ntust_course_watch"
LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
NOW = datetime(2026, 10, 11, 2, 0, 7, tzinfo=UTC)  # a Sunday morning in Taiwan, at second 7
CONFIG = """\
semester: "1151"
start: 2026-01-01T00:00:00+08:00
interval: 1.5
alert-interval: 60
"""


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py drops a plugin's modules when its setup fails (an invalid config), and the next load
    imports new ones, whose classes differ from those that the test modules imported.
    """
    kept = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(f"{PACKAGE}.")
    }
    yield
    sys.modules.update(kept)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reaches the network: aiohttp refuses every host but this machine's.

    The tests' local servers listen on 127.0.0.1; a plugin that a test failed to give its fake API
    would otherwise ask NTUST's real course query.
    """
    resolve = aiohttp.TCPConnector._resolve_host  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    async def local_only(
        connector: aiohttp.TCPConnector, host: str, port: int, traces: object = None
    ) -> object:
        if host not in LOCAL_HOSTS:
            msg = f"the tests do not reach the network: {host}"
            raise OSError(errno.EHOSTUNREACH, msg)  # aiohttp's error shows its strerror
        return await resolve(connector, host, port, cast("Any", traces))

    monkeypatch.setattr(aiohttp.TCPConnector, "_resolve_host", local_only)


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loop waits for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@pytest.fixture
def config() -> str | None:
    """The plugin's config.yaml, the bundled one unless a test parametrizes it."""
    return None


@pytest.fixture
async def bot(store: Store, tmp_path: Path, config: str | None) -> Bot:
    """A bot that loaded the plugin with ``config``, offline; its loop waits for READY."""
    return await load_plugin("NtustCourseWatch", tmp_path / "plugins", store, config=config)


@pytest.fixture
def cog(bot: Bot) -> NtustCourseWatch:
    """The loaded plugin's cog."""
    cog = bot.get_cog("NtustCourseWatch")
    assert cog is not None
    return cast("NtustCourseWatch", cog)


@dataclass
class Clock:
    """The loop's waits and clocks: a wait lasts until the test wakes it, then moves them on."""

    waits: list[float] = field(default_factory=list[float])
    woken: int = 0  # the waits that have ended
    time: float = 1000.0  # the monotonic clock
    now: datetime = NOW  # the aware wall clock
    _changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    def monotonic(self) -> float:
        """Stands for ``time.monotonic``."""
        return self.time

    def wall(self) -> datetime:
        """Stands for ``datetime.now(UTC)``."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move both clocks on."""
        self.time += seconds
        self.now += timedelta(seconds=seconds)

    async def sleep(self, seconds: float) -> None:
        """Record the wait, wait until :meth:`wake`, then move the clocks on by it."""
        async with self._changed:
            number = len(self.waits)
            self.waits.append(seconds)
            self._changed.notify_all()
            await self._changed.wait_for(lambda: self.woken > number)
        self.advance(seconds)

    async def wake(self) -> None:
        """End the waits that have started; later ones wait again."""
        async with self._changed:
            self.woken = len(self.waits)
            self._changed.notify_all()


type Answer = Course | Exception | None


@dataclass
class FakeApi:
    """NTUST's course query: answers per code, the last one repeating; an exception raises.

    Each answer takes ``delay`` seconds on the scene's clock.
    """

    clock: Clock
    answers: dict[str, list[Answer]] = field(default_factory=dict[str, list[Answer]])
    asked: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    delay: float = 0.0
    opened: int = 0
    closed: int = 0

    async def course(self, semester: str, code: str) -> Course | None:
        """Stands for ``Api.course``."""
        self.asked.append((semester, code))
        self.clock.advance(self.delay)
        answers = self.answers.get(code, [None])
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    @asynccontextmanager
    async def open(self) -> AsyncGenerator[FakeApi]:
        """Stands for ``open_api``: the session opens after READY and closes with the loop."""
        self.opened += 1
        try:
            yield self
        finally:
            self.closed += 1


@dataclass
class Scene:
    """The plugin loaded offline, its course query, channels, waits and clocks replaced."""

    bot: Bot
    ready: Ready
    api: FakeApi
    clock: Clock
    channels: dict[int, FakeChannel] = field(default_factory=dict[int, FakeChannel])

    @property
    def cog(self) -> NtustCourseWatch:
        """The loaded plugin's cog."""
        cog = self.bot.get_cog("NtustCourseWatch")
        assert cog is not None
        return cast("NtustCourseWatch", cog)

    def channel(self, channel_id: int, **_: object) -> FakeChannel:
        """Stands for ``bot.get_partial_messageable``: a channel that records its messages."""
        return self.channels.setdefault(channel_id, FakeChannel(sent=list[Sent](), id=channel_id))

    def posts(self, channel_id: int) -> list[dict[str, object]]:
        """The messages that ``channel_id`` got, as ``send``'s keyword arguments."""
        channel = self.channels.get(channel_id)
        return [] if channel is None else [fields for _, fields in channel.sent]

    async def steps(self, count: int) -> None:
        """Wait until the loop has made ``count`` steps, each ending in a wait, and its posts.

        Raises:
            TimeoutError: It did not within ``WAIT`` seconds.
            BaseException: The loop ended with it instead.
        """
        [task] = self.cog.tasks
        async with asyncio.timeout(WAIT):
            while len(self.clock.waits) < count:
                if task.done():
                    task.result()  # the loop's error
                    msg = "the loop ended"
                    raise AssertionError(msg)
                await asyncio.sleep(0)
            await asyncio.gather(*list(self.cog.posting))

    async def wake(self, steps: int) -> None:
        """Let the loop go on until it has made ``steps`` steps in all."""
        await self.clock.wake()
        await self.steps(steps)


@pytest.fixture
def scene_config() -> str:
    """The config.yaml of the scene's plugin; tests parametrize it."""
    return CONFIG


@pytest.fixture
async def scene(
    store: Store, tmp_path: Path, ready: Ready, scene_config: str, monkeypatch: pytest.MonkeyPatch
) -> Scene:
    """The loaded plugin, its course query, channels, waits and clocks replaced, before READY."""
    bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store, config=scene_config)
    clock = Clock()
    scene = Scene(bot, ready, FakeApi(clock), clock)
    monkeypatch.setattr(bot, "get_partial_messageable", scene.channel)
    cog = scene.cog
    cog.open_api = scene.api.open
    cog.sleep = clock.sleep
    cog.clock = clock.monotonic
    cog.now = clock.wall
    return scene
