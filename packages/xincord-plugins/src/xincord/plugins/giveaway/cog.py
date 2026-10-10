"""The command, the builder, the post's buttons and the automatic draw.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:44-633
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:16-380
"""

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.component_ids import ComponentIds

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .config import Config
    from .model import Draft

# v3's fields in v3's order, all text, and v3's prefix, so that v3's posts keep working.
IDS = ComponentIds("giveaway", ("action", "sub_action", "giveaway_id"), legacy_prefix="giveaway@")


@dataclass(frozen=True)
class Session:
    """A user's draft in a guild and the builder message that shows it."""

    message_id: int
    draft: Draft


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
        # Each user's draft per guild, by user ID and guild ID; v3's StepManager.steps.
        self.drafts: dict[tuple[int, int], Session] = {}

    async def create_giveaway(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the builder of a new draft for the user."""
        raise NotImplementedError
