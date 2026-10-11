"""Fixtures for the NtustAnnouncements tests: the plugin loads through its real entry point.

READY never comes unless a test sets it, so the boards' loops wait for it; the loops left running
are cancelled when the test ends. ``scene`` loads the plugin with two boards (the dormitory board
in channel 101 and the Language Center's recruitment board in channel 102), and replaces its web
(trimmed copies of NTUST's pages and a fake Gemini), its channels and its waits.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import pytest

from discord_fakes import FakeChannel, Sent
from plugin_fakes import FIXTURES, WAIT, Ready, load_plugin
from xincord.plugins.ntust_announcements.web import FetchError, Page

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.ntust_announcements.cog import NtustAnnouncements

PACKAGE = "xincord.plugins.ntust_announcements"
PAGES = FIXTURES / "plugins" / "ntust_announcements"
DORMITORY_URL = "https://student.ntust.edu.tw/p/403-1053-1436-1.php"
RECRUITMENT_URL = "https://lc.ntust.edu.tw/p/403-1070-1626-1.php"
CONFIG = f"""\
fetch-interval: 3600
api-keys:
  - "key-one"
prompt: "{{{{page_title}}}} {{{{page_url}}}} {{{{base_url}}}} {{{{now}}}} {{{{html}}}}"
boards:
  - name: STUDENT_DORMITORY
    url: "{DORMITORY_URL}"
    layout: student-affairs
    channel-id: 101
  - name: LANGUAGE_CENTER_RECRUITMENT
    url: "{RECRUITMENT_URL}"
    layout: language-center
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
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loops wait for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


def fixture_page(name: str) -> str:
    """A trimmed copy of an NTUST page."""
    return (PAGES / name).read_text(encoding="utf-8")


@dataclass
class Clock:
    """The loops' waits: each is recorded and lasts until the test wakes the waits so far."""

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
class FakeWeb:
    """NTUST's pages and Gemini: the boards' copies, a student article for every article.

    ``hold``, when set to an event, keeps page fetches waiting until it is set; prompts that name
    a URL in ``stuck`` never get an answer.
    """

    pages: dict[str, str] = field(
        default_factory=lambda: {
            DORMITORY_URL: fixture_page("student-dormitory.html"),
            RECRUITMENT_URL: fixture_page("language-center-recruitment.html"),
        }
    )
    article: str = field(default_factory=lambda: fixture_page("student-article.html"))
    answer: str = "Markdown"
    fetched: list[str] = field(default_factory=list[str])
    prompts: list[str] = field(default_factory=list[str])
    stuck: set[str] = field(default_factory=set[str])
    hold: asyncio.Event | None = None
    under_way: int = 0  # page fetches under way
    most: int = 0  # the most page fetches under way at once
    opened: int = 0
    closed: int = 0

    async def page(self, url: str) -> Page:
        self.fetched.append(url)
        self.under_way += 1
        self.most = max(self.most, self.under_way)
        try:
            if self.hold is not None:
                await self.hold.wait()
        finally:
            self.under_way -= 1
        text = self.pages.get(url, self.article if "/p/406-" in url else None)
        if text is None:
            raise FetchError(404)
        return Page(url, text)

    async def generate(self, key: str, prompt: str) -> str:
        del key
        self.prompts.append(prompt)
        if any(url in prompt for url in self.stuck):
            await asyncio.Event().wait()  # until cancelled
        return self.answer

    @asynccontextmanager
    async def open(self, model: str) -> AsyncGenerator[FakeWeb]:
        """Stands for ``open_web``: the session opens after READY and closes with the loops."""
        del model
        self.opened += 1
        try:
            yield self
        finally:
            self.closed += 1


@dataclass
class Scene:
    """The plugin loaded offline, its web, channels and waits replaced; READY not yet set."""

    bot: Bot
    ready: Ready
    web: FakeWeb
    clock: Clock
    sent: list[Sent] = field(default_factory=list[Sent])
    channels: dict[int, FakeChannel] = field(default_factory=dict[int, FakeChannel])

    @property
    def cog(self) -> NtustAnnouncements:
        """The loaded plugin's cog."""
        cog = self.bot.get_cog("NtustAnnouncements")
        assert cog is not None
        return cast("NtustAnnouncements", cog)

    def channel(self, channel_id: int, **_: object) -> FakeChannel:
        """Stands for ``bot.get_partial_messageable``: a channel that records its messages."""
        return self.channels.setdefault(channel_id, FakeChannel(sent=self.sent, id=channel_id))

    def posts(self, channel_id: int) -> list[str]:
        """The messages that ``channel_id`` got."""
        channel = self.channels.get(channel_id)
        return [] if channel is None else [str(fields["content"]) for _, fields in channel.sent]


@pytest.fixture
def config() -> str:
    """The plugin's config.yaml; tests parametrize it."""
    return CONFIG


@pytest.fixture
def web() -> FakeWeb:
    """NTUST's pages and Gemini for the loaded plugin."""
    return FakeWeb()


@pytest.fixture
async def bot(store: Store, tmp_path: Path, config: str) -> Bot:
    """A bot that loaded the plugin with ``config``, offline; its loops wait for READY."""
    return await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)


@pytest.fixture
async def scene(bot: Bot, ready: Ready, web: FakeWeb, monkeypatch: pytest.MonkeyPatch) -> Scene:
    """The loaded plugin with its web, channels and waits replaced, before READY."""
    scene = Scene(bot, ready, web, Clock())
    monkeypatch.setattr(bot, "get_partial_messageable", scene.channel)
    cog = scene.cog
    cog.open_web = scene.web.open
    cog.sleep = scene.clock.sleep
    return scene
