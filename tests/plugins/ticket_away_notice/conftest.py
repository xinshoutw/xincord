"""Fixtures for the TicketAwayNotice tests: the plugin loads through its real entry point.

Discord's REST requests are recorded instead of sent, and the bot has its user, as after a login.
``scene`` caches guilds 10 and 11 in discord.py, with the owner 20 a member of both and offline,
feeds their gateway events through discord.py's own parsers, and runs the notices' wait on a
``Clock`` that the test wakes.
"""

import asyncio
import re
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import pytest

import payloads
from discord_fakes import BOT_USER, FakeRest
from plugin_fakes import WAIT, add_guild, gateway, load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.ticket_away_notice.cog import TicketAwayNotice

PACKAGE = "xincord.plugins.ticket_away_notice"
GUILD = 10  # the watched guild
OTHER_GUILD = 11  # a guild that the config does not name, where the owner is a member too
OWNER = 20  # the member whose status decides the notice
GENERAL = 30  # a text channel of guild 10, the parent of new threads
# Guild 10 and owner 20, two ASCII prefixes and v3's 2 seconds; the bundled file waits for IDs.
CONFIG = """\
guild_id: 10
user_id: 20
prefix:
  - "ticket-"
  - "order-"
delay_millis: 2000
"""
POST = re.compile(r"POST /channels/(\d+)/messages")


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
def rest(monkeypatch: pytest.MonkeyPatch) -> FakeRest:
    """Discord's REST requests, recorded instead of sent; each answers at once."""
    recorded = FakeRest()
    recorded.install(monkeypatch)
    return recorded


@pytest.fixture(autouse=True)
def logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bot's user, which discord.py sets at the login, for v3's ``bot_*`` values."""
    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))


@pytest.fixture
def notice() -> str | None:
    """An operator's ``not-online.yaml``, or None for the bundled one; tests parametrize it."""
    return None


@pytest.fixture
async def bot(store: Store, tmp_path: Path, notice: str | None) -> Bot:
    """A bot that loaded TicketAwayNotice with `CONFIG` from `tmp_path / "plugins"`, offline.

    An operator's ``notice`` is in the plugin's lang directory first, where the load keeps it.
    """
    root = tmp_path / "plugins"
    if notice is not None:
        path = root / "TicketAwayNotice" / "lang" / "zh-TW" / "message" / "not-online.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(notice, encoding="utf-8")
    return await load_plugin("TicketAwayNotice", root, store, config=CONFIG)


@dataclass
class Clock:
    """The notices' wait: each sleep is recorded and lasts until the test wakes the clock."""

    delays: list[float] = field(default_factory=list[float])
    _slept: asyncio.Condition = field(default_factory=asyncio.Condition)
    _awake: asyncio.Event = field(default_factory=asyncio.Event)

    async def sleep(self, seconds: float) -> None:
        """Record the wait, then wait until :meth:`wake`."""
        async with self._slept:
            self.delays.append(seconds)
            self._slept.notify_all()
        await self._awake.wait()

    async def asleep(self, count: int = 1) -> None:
        """Wait until ``count`` waits have started.

        Raises:
            TimeoutError: They did not within ``WAIT`` seconds.
        """
        async with asyncio.timeout(WAIT), self._slept:
            await self._slept.wait_for(lambda: len(self.delays) >= count)

    def wake(self) -> None:
        """End every wait, and the later ones at once."""
        self._awake.set()


@dataclass
class Scene:
    """Guilds 10 and 11 in discord.py's cache, with TicketAwayNotice loaded.

    The owner 20 is a member of both, offline until :meth:`status` says otherwise. Each channel
    that :meth:`create` makes takes one notice, which ``rest`` records.
    """

    bot: Bot
    rest: FakeRest
    clock: Clock

    @property
    def cog(self) -> TicketAwayNotice:
        """The loaded plugin's cog.

        No isinstance check: a failed load makes discord.py import the plugin's modules again.
        """
        found = self.bot.get_cog("TicketAwayNotice")
        assert found is not None
        return cast("TicketAwayNotice", found)

    async def parse(self, event: str, payload: payloads.Payload) -> None:
        """Hand a gateway event to discord.py's parser and run the listeners it dispatched."""
        await gateway(self.bot, event, payload)

    async def create(
        self, channel_id: int, name: str, *, kind: int = 0, guild_id: int = GUILD
    ) -> None:
        """Somebody creates channel ``channel_id`` of type ``kind`` (0 text, 2 voice, 4 category,
        15 forum) named ``name`` in guild ``guild_id``."""
        self.answer(channel_id, guild_id)
        payload = payloads.channel(channel_id, name, kind=kind, guild_id=guild_id)
        await self.parse("CHANNEL_CREATE", payload)

    async def create_thread(self, thread_id: int, name: str, *, owner: int = 1) -> None:
        """User ``owner`` starts thread ``thread_id`` named ``name`` in channel ``GENERAL``."""
        self.answer(thread_id, GUILD)
        payload = payloads.thread(thread_id, GENERAL, GUILD, name)
        await self.parse(
            "THREAD_CREATE", {**payload, "owner_id": str(owner), "newly_created": True}
        )

    async def status(self, status: str) -> None:
        """The owner's status in guild 10 becomes ``status``, as Discord reports it."""
        await self.parse("PRESENCE_UPDATE", payloads.presence(OWNER, status, guild_id=GUILD))

    async def uncache_owner(self) -> None:
        """discord.py forgets the owner's member in guild 10, as if it never cached it."""
        payload: payloads.Payload = {"guild_id": str(GUILD), "user": payloads.user(OWNER, "owner")}
        await self.parse("GUILD_MEMBER_REMOVE", payload)

    def answer(self, channel_id: int, guild_id: int) -> None:
        """Let Discord answer one notice in ``channel_id`` with the message it created."""
        message = payloads.message(
            900 + channel_id, channel_id, guild_id, payloads.user(BOT_USER.id, BOT_USER.name)
        )
        self.rest.answers.setdefault(f"POST /channels/{channel_id}/messages", []).append(message)

    async def settle(self) -> None:
        """End the waits and wait until every notice is done; a failed one raises its error."""
        self.clock.wake()
        async with asyncio.timeout(WAIT):
            await asyncio.gather(*self.cog.notices)

    def notices(self) -> list[tuple[int, list[dict[str, Any]]]]:
        """Each notice posted, in order: its channel and its embeds without ``type`` and
        ``flags``, as the golden data has them."""
        posted: list[tuple[int, list[dict[str, Any]]]] = []
        for key, request in self.rest.sent:
            if (match := POST.fullmatch(key)) is None:
                continue
            body = cast("dict[str, Any]", request["json"])
            embeds = cast("list[dict[str, Any]]", body["embeds"])
            stripped = [
                {name: value for name, value in embed.items() if name not in {"type", "flags"}}
                for embed in embeds
            ]
            posted.append((int(match[1]), stripped))
        return posted


@pytest.fixture
async def scene(bot: Bot, rest: FakeRest) -> AsyncGenerator[Scene]:
    """Guilds 10 and 11 cached in the loaded bot, the owner offline in both.

    The notices still under way at the end are cancelled.
    """
    owner = payloads.member(OWNER, "owner")
    general = payloads.channel(GENERAL, "general")
    add_guild(bot, payloads.guild(GUILD, channels=[general], members=[owner]))
    add_guild(bot, payloads.guild(OTHER_GUILD, members=[owner]))
    created = Scene(bot, rest, Clock())
    cog = created.cog
    cog.sleep = created.clock.sleep
    yield created
    left = list(cog.notices)  # the cog may have left the bot
    for task in left:
        task.cancel()
    await asyncio.gather(*left, return_exceptions=True)
