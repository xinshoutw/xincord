"""The plugin's cog: the commands, the panels' buttons, the autocompletes and the voice lifecycle.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:16-140
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:56-957
"""

import random
from collections import OrderedDict
from typing import TYPE_CHECKING

from discord.ext import commands

from .commands import SEARCH_DEADLINE, Commands
from .emojis import FALLBACKS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .audio import Link, Player
    from .config import Config
    from .session import Session


class MusicPlayer(Commands, commands.Cog):
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

    def joined(self, guild_id: int, player: Player) -> None:
        """The bot is connecting in the guild: its session plays on ``player``."""
        self.session(guild_id).attach(player)

    def left(self, guild_id: int) -> None:
        """The bot left voice in the guild: its session forgets the songs."""
        if (session := self.sessions.get(guild_id)) is not None:
            session.detach()
