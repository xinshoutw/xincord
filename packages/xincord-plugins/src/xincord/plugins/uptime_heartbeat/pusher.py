"""One listener's loop: the REST ping, the push and its status code (v3's IntervalPusher class).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:15-136
"""

import logging
import time
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.http import Route

from .config import PING
from .logs import origin, redact

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

    @property
    def endpoint(self) -> str:
        """The listener's URL as the logs show it: its origin, without the push token."""
        return origin(self.listener.url)

    async def run(self) -> None:
        """Push at once, then again ``interval`` seconds after each attempt, until a 404.

        The delay follows each attempt, as v3's ``delay`` did, so the period is the interval plus
        the request time; ``discord.ext.tasks.loop`` would schedule from each start instead.
        """
        logger.info(
            "UptimeHeartbeat listener %d started (every %d s)",
            self.number,
            self.listener.interval,
        )
        while await self.push():
            await self.sleep(self.listener.interval)

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
                "UptimeHeartbeat listener %d could not measure the REST ping, "
                "so %%ping%% is -1: %s",
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
            # A network error needs no traceback. Its text can name the URL (aiohttp's connect
            # timeout does), so its URLs are cut to their origin too.
            logger.error(  # noqa: TRY400
                "UptimeHeartbeat listener %d: pushing to %s failed: %s",
                self.number,
                self.endpoint,
                redact(describe(error)),
            )
            return True
        except Exception as error:  # noqa: BLE001 - logged with its traceback below
            # Unexpected: the traceback shows where it failed. It is part of the message, with its
            # URLs cut to their origin: logger.exception would print the error's text as it is.
            logger.error(  # noqa: TRY400
                "UptimeHeartbeat listener %d: pushing to %s failed\n%s",
                self.number,
                self.endpoint,
                redact(format_traceback(error)),
            )
            return True
        return self.follow(status)

    def follow(self, status: int) -> bool:
        """Log a push's status code as v3 did; only a 404 stops the listener."""
        if status in SUCCESS:
            logger.debug(
                "UptimeHeartbeat listener %d pushed to %s (code %d)",
                self.number,
                self.endpoint,
                status,
            )
        elif status == NOT_FOUND:
            logger.warning(
                "UptimeHeartbeat listener %d stopped: the status monitor refused the push "
                "(code 404)",
                self.number,
            )
            return False
        elif status == ORIGIN_DOWN:
            logger.warning(
                "UptimeHeartbeat listener %d: the status monitor is offline (code 521)", self.number
            )
        else:
            logger.error(
                "UptimeHeartbeat listener %d: pushing to %s failed with code %d",
                self.number,
                self.endpoint,
                status,
            )
        return True


def describe(error: BaseException) -> str:
    """The error's message, or its type when it has none (aiohttp's timeouts may have none)."""
    return str(error) or type(error).__name__


def format_traceback(error: BaseException) -> str:
    """The error's traceback as ``logging`` prints it, without the last newline."""
    return "".join(traceback.format_exception(error)).rstrip("\n")
