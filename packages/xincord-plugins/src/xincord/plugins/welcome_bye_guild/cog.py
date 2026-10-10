"""The channel commands and the join and removal listeners.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:30-303
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    import discord
    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates


class WelcomeByeGuild(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates

    async def bind_channel(
        self,
        interaction: discord.Interaction,
        channel: app_commands.AppCommandChannel | None = None,
    ) -> None:
        """Stub until the commands exist."""
        raise NotImplementedError

    async def unbind_channel(self, interaction: discord.Interaction) -> None:
        """Stub until the commands exist."""
        raise NotImplementedError
