"""The listeners that post the away notice in new ticket channels while the owner is offline.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:11-39
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:26-29
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config


class TicketAwayNotice(commands.Cog):
    """The plugin's state and listeners; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the config and the notice's template.

        A reload builds a new cog from the files, as v3's ``reload()`` rebuilt its template.
        """
        self.bot = bot
        self.config = config
        self.lang = lang
        self.templates = templates
