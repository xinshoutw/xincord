"""The lobby commands, the voice listener and the checks when the bot is ready.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/DynamicVoiceChannel.kt:19-135
"""

import logging
from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

from .store import Binding, bind, unbind

if TYPE_CHECKING:
    import discord
    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

logger = logging.getLogger(__name__)


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
        """Bind ``channel``'s category and name as a lobby with the room formats (v3's ``bind``).

        A binding of the same category and name is replaced; v3 added a duplicate. The reply is
        ``bind-success``, or ``must-under-category`` for a channel outside a category, where
        nothing is stored.
        """
        guild = interaction.guild
        if guild is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        if channel.category_id is None:
            await self._reply(interaction, "must-under-category")
            return
        binding = Binding(channel.category_id, channel.name, format_name_1, format_name_2)
        await bind(self.store, guild.id, binding)
        logger.info(
            "DynamicVoiceChannel bound the lobby %r of category %s in guild %s",
            channel.name,
            channel.category_id,
            guild.id,
        )
        await self._reply(interaction, "bind-success")

    async def unbind_lobby(
        self, interaction: discord.Interaction, channel: app_commands.AppCommandChannel
    ) -> None:
        """Remove the bindings of ``channel``'s category and current name (v3's ``unbind``).

        The reply is ``unbind-success``, ``unbind-fail`` when there was no such binding, or
        ``must-under-category`` for a channel outside a category.
        """
        guild = interaction.guild
        if guild is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        if channel.category_id is None:
            await self._reply(interaction, "must-under-category")
            return
        removed = await unbind(self.store, guild.id, channel.category_id, channel.name)
        if removed:
            logger.info(
                "DynamicVoiceChannel unbound the lobby %r of category %s in guild %s",
                channel.name,
                channel.category_id,
                guild.id,
            )
        await self._reply(interaction, "unbind-success" if removed else "unbind-fail")

    async def _reply(self, interaction: discord.Interaction, key: str) -> None:
        """Edit the deferred response into the message ``key``, in the user's locale, as v3.

        The values are v3's ``Placeholder.get(event)``, which threw outside text channels.
        """
        template = self.templates.message(key, interaction.locale.value)
        message = render_message(template, placeholder_values(interaction))
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )
