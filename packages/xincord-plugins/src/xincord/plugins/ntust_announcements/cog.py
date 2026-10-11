"""The plugin's cog: the boards' loops, their posts and the ready check.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:15-95
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-43
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:117-153
"""

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING

from discord.ext import commands

from .web import open_web

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from xincord.core.storage import Store

    from .config import Config
    from .watch import Sleep
    from .web import Requests

type OpenWeb = Callable[[str], AbstractAsyncContextManager[Requests]]  # the model to a session


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
        self.task: asyncio.Task[None] | None = None  # the boards' loops, from READY
        # The effects that tests replace: the waits, the clocks and the web.
        self.sleep: Sleep = asyncio.sleep
        self.clock: Callable[[], float] = time.monotonic
        self.now: Callable[[], datetime] = datetime.now  # the host's local time, as v3's
        self.open_web: OpenWeb = open_web
