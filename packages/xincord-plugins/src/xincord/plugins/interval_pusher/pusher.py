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
        """Push once and log the outcome; return whether the listener keeps pushing."""
        raise NotImplementedError


def describe(error: BaseException) -> str:
    """The error's message, or its type when it has none (aiohttp's timeouts may have none)."""
    return str(error) or type(error).__name__
