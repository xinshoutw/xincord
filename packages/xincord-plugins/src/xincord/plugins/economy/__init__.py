"""Economy: each guild's wallets of money and spending, which listed administrators change.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Event.kt:26-131
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import Economy
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()  # v3's GoogleSheetAPI served only the dead Sheets storage (B12)
SOFT_DEPENDS: tuple[str, ...] = ()
# Discord resolves the member option in the interaction, and nothing reads the member cache.
INTENTS = discord.Intents.none()
# Replies use the user's locale and fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files, the templates and the config, then add the cog.

    The lang files load first, so that they are written even while the config waits for an
    administrator. The wallets are in the shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    templates = Templates.load(lang)
    await bot.add_cog(Economy(context.config(Config), context.store, lang, templates))
