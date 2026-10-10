"""The command, the builder, the post's buttons and the automatic draw.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:44-633
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:16-380
"""

import random
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .config import Config


class Giveaway(commands.Cog):
    """The plugin's state, handlers and loop; ``setup`` registers them."""

    def __init__(
        self, bot: commands.Bot, config: Config, store: Store, lang: Lang, templates: Templates
    ) -> None:
        """Keep the bot, the config, the store and what ``setup`` loaded."""
        self.bot = bot
        self.config = config
        self.store = store
        self.lang = lang
        self.templates = templates
        # The winners' draws: the operating system's randomness, never a seeded generator.
        self.random: random.Random = random.SystemRandom()
