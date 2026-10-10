"""The loops that push each listener's URL, from READY until the plugin unloads.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/Event.kt:10-54
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:54-135
"""

import asyncio
from typing import TYPE_CHECKING, override

from discord.ext import commands

from .pusher import Pusher, get_status, open_session, rest_ping

if TYPE_CHECKING:
    from .config import Config, Listener
    from .pusher import Sleep


class UptimeHeartbeat(commands.Cog):
    """The plugin's state and loops; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config) -> None:
        """Keep the bot and the configured listeners, in the config's order."""
        self.bot = bot
        self.listeners = config.listeners
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # one loop per listener once loaded
        self.sleep: Sleep = asyncio.sleep  # the delay between pushes, which tests replace

    @override
    async def cog_load(self) -> None:
        """Start one loop per listener; each waits until the bot is ready.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is pushed before READY. In a ready bot, as after a reload, the loops push at once: v3
        started its pushers when it loaded, after JDA was ready.
        """
        self.tasks = tuple(
            asyncio.create_task(
                self._push(number, listener), name=f"UptimeHeartbeat listener {number}"
            )
            for number, listener in enumerate(self.listeners, start=1)
        )

    @override
    async def cog_unload(self) -> None:
        """Cancel the loops and wait for them, so that their HTTP sessions are closed.

        No failure ends a loop, so this is where they end. A reload builds a new cog from the new
        config, as v3's ``reload()`` restarted every pusher.
        """
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def _push(self, number: int, listener: Listener) -> None:
        """Wait until the bot is ready, then run the listener's loop with its own session."""
        await self.bot.wait_until_ready()
        async with open_session() as session:
            pusher = Pusher(
                number,
                listener,
                get=lambda url: get_status(session, url),
                ping=lambda: rest_ping(self.bot),
                sleep=self.sleep,
            )
            await pusher.run()
