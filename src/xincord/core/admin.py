"""Commands for the bot owner: ``/xincord reload``."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands

if TYPE_CHECKING:
    from xincord.core.bot import Bot

NOT_OWNER = "Only the bot owner can use this command."
MAX_CHOICES = 25  # Discord shows at most 25 autocomplete suggestions


class Xincord(
    app_commands.Group,
    name="xincord",
    description="Manage the bot",
    guild_only=True,
    default_permissions=discord.Permissions(),
):
    """``/xincord``: commands for the bot owner; only administrators see it by default."""

    @app_commands.command(description="Reload the config and the plugins, or one plugin")
    @app_commands.describe(plugin="Plugin to reload with the plugins that depend on it")
    async def reload(self, interaction: discord.Interaction, plugin: str | None = None) -> None:
        """Reload for the owner and reply with the summary."""
        bot = cast("Bot", interaction.client)
        # The command tree has deferred the response ephemerally.
        if not await bot.is_owner(interaction.user):
            await interaction.followup.send(NOT_OWNER, ephemeral=True)
            return
        await interaction.followup.send(await bot.reload(plugin), ephemeral=True)

    @reload.autocomplete("plugin")
    async def plugin_names(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest the loaded plugins whose name contains ``current``."""
        bot = cast("Bot", interaction.client)
        names = [name for name in bot.loaded if current.casefold() in name.casefold()]
        return [app_commands.Choice(name=name, value=name) for name in names[:MAX_CHOICES]]
