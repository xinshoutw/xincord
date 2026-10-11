"""The plugin's cog: the boards' loops, their posts and the ready check.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:15-95
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-43
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:117-153
"""

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, override

import discord
from discord.ext import commands

from .gemini import Gemini
from .store import Posted
from .watch import Watcher
from .web import open_web

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from xincord.core.storage import Store

    from .config import Config
    from .watch import Sleep
    from .web import Page, Requests

type OpenWeb = Callable[[str], AbstractAsyncContextManager[Requests]]  # the model to a session

FETCHES = 5  # NTUST pages fetched at a time, v3's maxConcurrentRequests
NO_MENTIONS = discord.AllowedMentions.none()  # Gemini's text pings nobody (v3: JDA's default)


class NtustAnnouncements(commands.Cog):
    """The plugin's state; ``setup`` adds it."""

    def __init__(self, bot: commands.Bot, config: Config, store: Store) -> None:
        """Keep the bot, the config and the store of the boards' posted lists.

        A reload builds a new cog from the new config: v3's reload kept the keys, the prompt and
        the interval that it had read first.
        """
        self.bot = bot
        self.config = config
        self.store = store
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # the boards' loops, from READY
        # The effects that tests replace: the waits, the clocks and the web.
        self.sleep: Sleep = asyncio.sleep
        self.clock: Callable[[], float] = time.monotonic
        self.now: Callable[[], datetime] = datetime.now  # the host's local time, as v3's
        self.open_web: OpenWeb = open_web

    @override
    async def cog_load(self) -> None:
        """Start the boards' loops; they wait until the bot is ready.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is fetched before READY. In a ready bot, as after a reload, the boards pass at once: v3
        started its scheduler when it loaded, after JDA was ready, with no initial delay.
        """
        self.tasks = (asyncio.create_task(self._run(), name="NtustAnnouncements"),)

    @override
    async def cog_unload(self) -> None:
        """Cancel the loops and wait for them, so that their session closes.

        A reload builds a new cog with the new config; v3's reload added a second scheduler to the
        first (duplicate posts) or failed after a disable.
        """
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def _run(self) -> None:
        """Wait until the bot is ready, then run one loop per board over one session.

        Each board passes at once, then ``fetch-interval`` seconds after its own pass, so a board
        whose announcement waits hours between Gemini attempts holds up no other; v3 ran all the
        boards in one cycle, five at a time, each holding its slot through Gemini's waits.
        """
        await self.bot.wait_until_ready()
        fetches = asyncio.Semaphore(FETCHES)
        async with self.open_web(self.config.model) as web:

            async def page(url: str) -> Page:
                async with fetches:  # held while fetching only
                    return await web.page(url)

            gemini = Gemini(
                self.config.api_keys,
                self.config.prompt,
                web.generate,
                self.sleep,
                self.clock,
                self.now,
            )
            posted = Posted(self.store)
            async with asyncio.TaskGroup() as boards:
                for board in self.config.boards:
                    watcher = Watcher(board, page, gemini.convert, self._send, posted)
                    boards.create_task(
                        watcher.run(self.config.fetch_interval, self.sleep), name=watcher.name
                    )

    async def _send(self, channel_id: int, content: str) -> None:
        """Post one message to a board's channel, which needs no cache, pinging nobody."""
        channel = self.bot.get_partial_messageable(channel_id)
        await channel.send(content=content, allowed_mentions=NO_MENTIONS)
