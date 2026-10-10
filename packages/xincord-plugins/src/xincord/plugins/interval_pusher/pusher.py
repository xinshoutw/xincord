"""One listener's loop: the REST ping, the push and its status code (v3's IntervalPusher class).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:15-136
"""

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.http import Route

from .config import PING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .config import Listener

type Get = Callable[[str], Awaitable[int]]  # sends one push and returns its status code
type Ping = Callable[[], Awaitable[int]]  # measures the REST ping in milliseconds
type Sleep = Callable[[float], Awaitable[object]]

logger = logging.getLogger(__name__)

NO_PING = -1  # what %ping% becomes when the ping cannot be measured, as in v3
# A failed ping: Discord's errors, aiohttp's, and OSError for the network, timeouts included.
PING_ERRORS = (discord.DiscordException, aiohttp.ClientError, OSError)
# v3's limits: 10 seconds to connect and 30 seconds for the whole request.
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)
# A push that did not reach the monitor: aiohttp's errors and OSError, timeouts included.
NETWORK_ERRORS = (aiohttp.ClientError, OSError)
SUCCESS = range(200, 300)
NOT_FOUND = 404  # Uptime Kuma's answer for an unknown or paused push token: stop, as v3
ORIGIN_DOWN = 521  # Cloudflare's answer when the monitor behind it is offline


def build_url(template: str, ping: int) -> str:
    """Replace every ``%ping%`` in ``template`` with ``ping``, as v3's ``String.replace``."""
    return template.replace(PING, str(ping))


async def rest_ping(client: discord.Client, clock: Callable[[], float] = time.perf_counter) -> int:
    """Time a ``GET /users/@me`` request to Discord in whole milliseconds.

    JDA's ``getRestPing()`` timed the same request; discord.py has no REST ping, and this is the
    request that its own login sends.
    """
    start = clock()
    await client.http.request(Route("GET", "/users/@me"))
    return round((clock() - start) * 1000)


def open_session() -> aiohttp.ClientSession:
    """An HTTP session for one listener's pushes, with v3's limits; the caller closes it."""
    return aiohttp.ClientSession(timeout=TIMEOUT)


async def get_status(session: aiohttp.ClientSession, url: str) -> int:
    """Send one push, a GET that follows no redirect as in v3, and return its status code.

    The body is not read: v3 read it into a string and ignored it.
    """
    async with session.get(url, allow_redirects=False) as response:
        return response.status


@dataclass(frozen=True)
class Pusher:
    """One listener's loop, with the request, the ping and the delay passed in."""

    number: int  # the listener's position in the config, from 1, for the logs
    listener: Listener
    get: Get
    ping: Ping
    sleep: Sleep

    async def run(self) -> None:
        """Push at once, then again ``interval`` seconds after each attempt, until a 404."""
        raise NotImplementedError

    async def url(self) -> str:
        """The listener's URL with the REST ping in place of ``%ping%``, or ``-1`` if it fails.

        Discord is asked only when the URL uses the ping; v3 asked at every push.
        """
        template = self.listener.url
        if PING not in template:
            return template
        try:
            ping = await self.ping()
        except PING_ERRORS as error:
            logger.warning(
                "IntervalPusher listener %d could not measure the REST ping, so %%ping%% is -1: %s",
                self.number,
                describe(error),
            )
            ping = NO_PING
        return build_url(template, ping)

    async def push(self) -> bool:
        """Push once and log the outcome at v3's levels; return whether to keep pushing.

        A cancelled push raises ``CancelledError``, which is no ``Exception``, and logs nothing;
        v3 caught the cancellation while it waited for the ping and logged a spurious failure.
        """
        try:
            url = await self.url()
            status = await self.get(url)
        except NETWORK_ERRORS as error:
            # The URL as configured, as v3 logged it; a network error needs no traceback.
            logger.error(  # noqa: TRY400
                "IntervalPusher listener %d: pushing to %s failed: %s",
                self.number,
                self.listener.url,
                describe(error),
            )
            return True
        except Exception:
            # Unexpected: the traceback shows where it failed.
            logger.exception(
                "IntervalPusher listener %d: pushing to %s failed", self.number, self.listener.url
            )
            return True
        return self.follow(url, status)

    def follow(self, url: str, status: int) -> bool:
        """Log a push's status code as v3 did; only a 404 stops the listener."""
        if status in SUCCESS:
            logger.debug("IntervalPusher listener %d pushed %s", self.number, url)
        elif status == NOT_FOUND:
            logger.warning(
                "IntervalPusher listener %d stopped: the status monitor refused the push "
                "(code 404)",
                self.number,
            )
            return False
        elif status == ORIGIN_DOWN:
            logger.warning(
                "IntervalPusher listener %d: the status monitor is offline (code 521)", self.number
            )
        else:
            logger.error(
                "IntervalPusher listener %d: pushing to %s failed with code %d",
                self.number,
                url,
                status,
            )
        return True


def describe(error: BaseException) -> str:
    """The error's message, or its type when it has none (aiohttp's timeouts may have none)."""
    return str(error) or type(error).__name__
