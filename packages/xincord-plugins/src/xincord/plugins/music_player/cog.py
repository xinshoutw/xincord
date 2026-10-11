"""The plugin's cog: the commands, the panels' buttons, the autocompletes and the voice lifecycle.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:16-140
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:56-957
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config


class MusicPlayer(commands.Cog):
    """The plugin's state and handlers; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep the bot and what ``setup`` loaded."""
        self.bot = bot
        self.config = config
        self.lang = lang
        self.templates = templates
