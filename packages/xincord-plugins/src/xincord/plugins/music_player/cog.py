"""The plugin's cog: the commands, the panels' buttons, the autocompletes and the voice lifecycle.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:16-140
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:56-957
"""

import asyncio
import logging
import random
from collections import OrderedDict
from functools import partial
from typing import TYPE_CHECKING, cast, override

import discord
from discord.ext import commands

from .buttons import Buttons
from .commands import SEARCH_DEADLINE, Commands
from .emojis import FALLBACKS, resolve
from .node import open_link
from .panels import Panels
from .texts import describe

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine, Mapping

    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .audio import EndReason, Link, Listener, Player
    from .config import Config, Node
    from .panels import Panel

    type OpenLink = Callable[[int, Node, Listener], Link]
    type Sleep = Callable[[float], Awaitable[object]]
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
        self.tasks: set[asyncio.Task[None]] = set()  # started by events; the unload awaits them
        self.starting: asyncio.Task[None] | None = None  # the startup, from READY
        self.open_link: OpenLink = open_link  # tests give a fake node
        self.sleep: Sleep = asyncio.sleep  # the idle leave's wait; tests replace it
        self.idle: dict[int, asyncio.Task[None]] = {}  # each idle guild's leave, by guild
        self.closed = False  # set by the unload, after which nothing starts

    @override
    async def cog_load(self) -> None:
        """Start the startup task: it waits for READY, then connects to the node.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so
        nothing is requested before READY; a plugin reloaded into a ready bot starts at once.
        """
        self.starting = asyncio.create_task(self.start(), name="MusicPlayer startup")
        self.starting.add_done_callback(_failed)

    @override
    async def cog_unload(self) -> None:
        """Leave voice in every guild, delete the panels and close the node's client.

        v3's unload left its players, connections and threads running (bug B23): a reload stops
        the music now. Work under way ends first, so that nothing starts after the unload.
        """
        self.closed = True
        waiting = [cast("asyncio.Task[None]", self.starting), *self.idle.values()]
        for task in waiting:
            task.cancel()
        await asyncio.gather(*waiting, return_exceptions=True)
        if self.link is not None:
            await self.link.close()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.panels.close()

    async def start(self) -> None:
        """At READY: the link to the node, then the application's emojis (v3 read them at first
        use, blocking an event thread, and broke every panel when one was missing)."""
        await self.bot.wait_until_ready()
        user = cast("discord.ClientUser", self.bot.user)
        self.link = self.open_link(user.id, self.config.lavalink, self)
        try:
            found = await self.bot.fetch_application_emojis()
        except discord.HTTPException as error:
            logger.warning(
                "MusicPlayer: the application's emojis could not be read (%s); Unicode emojis "
                "stand for them",
                describe(error),
            )
            return
        self.emojis, missing = resolve(
            self.config.emojis, {emoji.name: str(emoji) for emoji in found}
        )
        if missing:
            logger.warning(
                "MusicPlayer: the application has no emoji named %s; Unicode emojis stand for them",
                ", ".join(missing),
            )

    @override
    def changed(self, session: Session) -> None:
        """A session started or stopped playing, or connected or left: start or end its wait.

        A connected session with nothing playing leaves voice after ``auto_leave_timeout`` (0:
        never); a song that starts, or a disconnection, ends the wait. v3 declared the timeout and
        never left (bug B10).
        """
        guild_id = session.guild_id
        if session.player is not None and not session.playing:
            timeout = self.config.player.auto_leave_timeout
            if timeout and not self.closed and guild_id not in self.idle:
                task = asyncio.create_task(
                    self.leave_when_idle(session, timeout / 1000), name="MusicPlayer idle"
                )
                self.idle[guild_id] = task
                task.add_done_callback(partial(self._idle_ended, guild_id))
            return
        if (
            task := self.idle.pop(guild_id, None)
        ) is not None and task is not asyncio.current_task():
            task.cancel()

    async def leave_when_idle(self, session: Session, seconds: float) -> None:
        """Wait ``seconds``, then leave voice: nothing started meanwhile, or the wait was ended."""
        await self.sleep(seconds)
        guild = cast("discord.Guild", self.bot.get_guild(session.guild_id))
        logger.info(
            "MusicPlayer: guild %d: nothing played for %g seconds; leaving voice",
            session.guild_id,
            seconds,
        )
        await cast("discord.VoiceProtocol", guild.voice_client).disconnect(force=True)

    def _idle_ended(self, guild_id: int, task: asyncio.Task[None]) -> None:
        """Forget a finished wait, and log the error that ended it."""
        if self.idle.get(guild_id) is task:
            del self.idle[guild_id]
        _failed(task)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """The bot left a guild: leave its voice and forget its player, songs, volume and panels.

        v3 kept its managers forever (bug B16).
        """
        if (voice := guild.voice_client) is not None:
            await voice.disconnect(force=True)
        self.sessions.pop(guild.id, None)
        await self.panels.close_guild(guild.id)

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

    async def ended(self, guild_id: int, number: int, reason: EndReason) -> None:
        """The node ended the guild's song started as ``number``: its session follows."""
        if (session := self.sessions.get(guild_id)) is not None:
            await session.ended(number, reason)

    async def stuck(self, guild_id: int, number: int) -> None:
        """The node reported the guild's song started as ``number`` stuck."""
        if (session := self.sessions.get(guild_id)) is not None:
            await session.stuck(number)

    def left(self, guild_id: int) -> None:
        """The bot left voice in the guild: its session forgets the songs, its panels go."""
        if (session := self.sessions.get(guild_id)) is not None:
            session.detach()
        self.spawn(self.panels.close_guild(guild_id))


def _failed(task: asyncio.Task[None]) -> None:
    """Log the error that ended a task: nothing awaits it until the unload."""
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error("MusicPlayer: a task failed", exc_info=error)
