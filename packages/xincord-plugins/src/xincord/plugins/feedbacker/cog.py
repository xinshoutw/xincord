"""The feedback form: the command, the star buttons and the feedback modal.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:23-161
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config


class Feedbacker(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.config = config
        self.lang = lang
        self.templates = templates
