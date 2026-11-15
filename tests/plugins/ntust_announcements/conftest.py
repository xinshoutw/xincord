"""Fixtures for the NtustAnnouncements tests: the plugin loads through its real entry point.

READY never comes unless a test sets it, so the feed's loop waits for it; the loops left running
are cancelled when the test ends. ``scene`` loads the plugin with two boards (the dormitory board
in channel 101 and the Language Center's recruitment board in channel 102), and replaces
bulletin's API, the channels, the waits and the clock.
"""

import asyncio
import errno
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import pytest

from bulletin_fakes import Clock, FakeApi
from discord_fakes import FakeChannel, Sent
from plugin_fakes import WAIT, Ready, load_plugin

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.ntust_announcements.cog import NtustAnnouncements

PACKAGE = "xincord.plugins.ntust_announcements"
LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
CONFIG = """\
poll-interval: 60
rendition-wait: 3600
boards:
  - name: STUDENT_DORMITORY
    board: "1053-1436"
    channel-id: 101
  - name: LANGUAGE_CENTER_RECRUITMENT
    board: "1070-1626"
    channel-id: 102
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

    A plugin that a test failed to give its fake API would otherwise read bulletin's real feed.
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
    """READY for the offline bots: the loops wait for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@dataclass
class Waits:
    """The loop's waits: each is recorded and lasts until the test wakes the waits so far."""

    waits: list[float] = field(default_factory=list[float])
    woken: int = 0  # the waits that have ended
    _changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    async def sleep(self, seconds: float) -> None:
        """Record the wait, then wait until :meth:`wake`."""
        async with self._changed:
            number = len(self.waits)
            self.waits.append(seconds)
            self._changed.notify_all()
            await self._changed.wait_for(lambda: self.woken > number)

    async def asleep(self, count: int) -> None:
        """Wait until ``count`` waits have started.

        Raises:
            TimeoutError: They did not within ``WAIT`` seconds.
        """
        async with asyncio.timeout(WAIT), self._changed:
            await self._changed.wait_for(lambda: len(self.waits) >= count)

    async def wake(self) -> None:
        """End the waits that have started; later ones wait again."""
        async with self._changed:
            self.woken = len(self.waits)
            self._changed.notify_all()


@dataclass
class Scene:
    """The plugin loaded offline, its API, channels, waits and clock replaced; READY not yet set."""

    bot: Bot
    ready: Ready
    api: FakeApi = field(default_factory=FakeApi)
    waits: Waits = field(default_factory=Waits)
    clock: Clock = field(default_factory=Clock)
    channels: dict[int, FakeChannel] = field(default_factory=dict[int, FakeChannel])
    opened: list[str] = field(default_factory=list[str])  # the API's URL of each session
    closed: int = 0

    @property
    def cog(self) -> NtustAnnouncements:
        """The loaded plugin's cog."""
        cog = self.bot.get_cog("NtustAnnouncements")
        assert cog is not None
        return cast("NtustAnnouncements", cog)

    @asynccontextmanager
    async def open(self, url: str) -> AsyncGenerator[FakeApi]:
        """Stands for ``open_bulletin``: the session opens after READY and closes with the loop."""
        self.opened.append(url)
        try:
            yield self.api
        finally:
            self.closed += 1

    def channel(self, channel_id: int, **_: object) -> FakeChannel:
        """Stands for ``bot.get_partial_messageable``: a channel that records its messages."""
        return self.channels.setdefault(channel_id, FakeChannel(sent=list[Sent](), id=channel_id))

    def posts(self, channel_id: int) -> list[dict[str, Any]]:
        """The fields of each message that ``channel_id`` got."""
        channel = self.channels.get(channel_id)
        return [] if channel is None else [fields for _, fields in channel.sent]


@pytest.fixture
def config() -> str:
    """The plugin's config.yaml; tests parametrize it."""
    return CONFIG


@pytest.fixture
async def bot(store: Store, tmp_path: Path, config: str) -> Bot:
    """A bot that loaded the plugin with ``config``, offline; its loop waits for READY."""
    return await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)


@pytest.fixture
async def scene(bot: Bot, ready: Ready, monkeypatch: pytest.MonkeyPatch) -> Scene:
    """The loaded plugin with its API, channels, waits and clock replaced, before READY."""
    scene = Scene(bot, ready)
    monkeypatch.setattr(bot, "get_partial_messageable", scene.channel)
    cog = scene.cog
    cog.open_bulletin = scene.open
    cog.sleep = scene.waits.sleep
    cog.now = scene.clock.now
    return scene
