"""The lobby commands, the voice listener and the checks when the bot is ready.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/DynamicVoiceChannel.kt:19-135
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    import discord
    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates


class DynamicVoiceChannel(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates

    async def bind_lobby(
        self,
        interaction: discord.Interaction,
        channel: app_commands.AppCommandChannel,
        format_name_1: str,
        format_name_2: str,
    ) -> None:
        """Bind ``channel``'s category and name as a lobby with the room formats (v3's ``bind``)."""
        raise NotImplementedError

    async def unbind_lobby(
        self, interaction: discord.Interaction, channel: app_commands.AppCommandChannel
    ) -> None:
        """Remove the bindings of ``channel``'s category and current name (v3's ``unbind``)."""
        raise NotImplementedError
