"""The plugin's cog: the commands, the panels' buttons, the autocompletes and the voice lifecycle.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:16-140
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:56-957
"""

import asyncio
import logging
import random
from collections import OrderedDict
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .buttons import Buttons
from .commands import SEARCH_DEADLINE, Commands
from .emojis import FALLBACKS
from .panels import Panels

if TYPE_CHECKING:
    from collections.abc import Coroutine, Mapping

    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .audio import Link, Player
    from .config import Config
    from .panels import Panel
    from .session import Session


logger = logging.getLogger(__name__)


class MusicPlayer(Commands, Buttons, commands.Cog):
    """The plugin's state and handlers; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep the bot and what ``setup`` loaded; no session, no link until READY.

        Until the application's emojis are read at READY, the Unicode ones stand for them.
        """
        self.bot = bot
        self.config = config
        self.lang = lang
        self.templates = templates
        self.sessions: dict[int, Session] = {}
        self.link: Link | None = None
        self.emojis: Mapping[str, str] = FALLBACKS
        self.random: random.Random = random.SystemRandom()  # /shuffle's order; tests seed it
        # v3's cache of autocomplete searches by input, the oldest out first; a reload clears it.
        self.searches: OrderedDict[str, tuple[app_commands.Choice[str], ...]] = OrderedDict()
        self.search_deadline = SEARCH_DEADLINE  # seconds; tests shorten it
        self.panels = Panels(self.refresh_panel)
        self.tasks: set[asyncio.Task[None]] = (
            set()
        )  # work started by events, which the unload awaits

    async def refresh_panel(self, panel: Panel) -> bool:
        """Edit ``panel`` with the guild's current song; False once Discord refused the edit.

        Nothing plays: the panel stays as it is, as in v3. The queue panel shows the current
        queue (v3's refreshes of it always failed, bug B6).
        """
        session = self.sessions.get(panel.guild_id)
        if session is None or not session.playing:
            return True
        message = self.render(panel.screen, session, panel.interaction)
        try:
            await panel.interaction.edit_original_response(
                content=message.content, embeds=list(message.embeds), view=message.view
            )
        except discord.HTTPException as error:
            logger.debug("MusicPlayer: panel %d stopped: %s", panel.message_id, error)
            return False
        return True

    def spawn(self, work: Coroutine[object, object, None]) -> None:
        """Run ``work`` as a task that the unload waits for, logging the error that ends it."""
        task = asyncio.create_task(work, name="MusicPlayer")
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(_failed)

    def joined(self, guild_id: int, player: Player) -> None:
        """The bot is connecting in the guild: its session plays on ``player``."""
        self.session(guild_id).attach(player)

    def left(self, guild_id: int) -> None:
        """The bot left voice in the guild: its session forgets the songs, its panels go."""
        if (session := self.sessions.get(guild_id)) is not None:
            session.detach()
        self.spawn(self.panels.close_guild(guild_id))


def _failed(task: asyncio.Task[None]) -> None:
    """Log the error that ended a task: nothing awaits it until the unload."""
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error("MusicPlayer: a task failed", exc_info=error)
