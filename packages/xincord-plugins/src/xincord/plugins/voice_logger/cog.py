"""The settings menu, its components, the voice and status listeners and the checks at READY.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:29-439
"""

from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.component_ids import ComponentIds

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("voice_logger", ("action",), legacy_prefix="voice-logger@")


class VoiceLogger(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the current channel's settings menu.

        Raises:
            NotImplementedError: Not implemented yet.
        """
        raise NotImplementedError
