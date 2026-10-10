"""The wallet commands, the boards and v3's balance button.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:18-203
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .config import Config


class Economy(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the store and what ``setup`` loaded."""
        self.config = config
        self.store = store
        self.lang = lang
        self.templates = templates

    async def show_balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member | discord.User | None = None,
    ) -> None:
        """Stub."""
        raise NotImplementedError
