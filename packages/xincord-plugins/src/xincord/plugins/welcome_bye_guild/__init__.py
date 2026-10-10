"""WelcomeByeGuild: members who join or leave a guild are welcomed or seen off in bound channels.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/Event.kt:18-80
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import WelcomeByeGuild

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Member joins and removals need the privileged members intent, which v3's core always requested.
INTENTS = discord.Intents(members=True)
# Replies and messages use the guild's locale and fall back to this one, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog.

    The plugin has no config: v3's only key was ``enabled``. Its data is in the shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    await bot.add_cog(WelcomeByeGuild(bot, context.store, lang, Templates.load(lang)))
