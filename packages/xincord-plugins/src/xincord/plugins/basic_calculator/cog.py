"""The /basic-calculate command and its replies.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BasicCalculator/src/main/kotlin/basiccalculator/BasicCalculator.kt:14-61
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates


class BasicCalculator(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.lang = lang
        self.templates = templates
