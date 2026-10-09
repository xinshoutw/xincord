"""The example command and its counter button.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/_Example.kt:11-43
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config


class Example(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.config = config
        self.lang = lang
        self.templates = templates

    async def reply(
        self, interaction: discord.Interaction, option1: str, option2: int | None
    ) -> None:
        """Stub until the reply exists."""
        raise NotImplementedError
