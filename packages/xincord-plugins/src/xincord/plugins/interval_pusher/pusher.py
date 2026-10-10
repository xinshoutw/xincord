"""One listener's loop: the REST ping, the push and its status code (v3's IntervalPusher class).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:15-136
"""

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord

    from .config import Listener

type Get = Callable[[str], Awaitable[int]]  # sends one push and returns its status code
type Ping = Callable[[], Awaitable[int]]  # measures the REST ping in milliseconds
type Sleep = Callable[[float], Awaitable[object]]


def build_url(template: str, ping: int) -> str:
    """Replace every ``%ping%`` in ``template`` with ``ping``."""
    raise NotImplementedError


async def rest_ping(client: discord.Client, clock: Callable[[], float] = time.perf_counter) -> int:
    """Time a ``GET /users/@me`` request to Discord in whole milliseconds."""
    raise NotImplementedError


@dataclass(frozen=True)
class Pusher:
    """One listener's loop, with the request, the ping and the delay passed in."""

    number: int  # the listener's position in the config, from 1, for the logs
    listener: Listener
    get: Get
    ping: Ping
    sleep: Sleep

    async def url(self) -> str:
        """The listener's URL with the REST ping in place of ``%ping%``."""
        raise NotImplementedError
