"""Commands for the bot owner: ``/xincord reload``.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:60-93
"""

import discord
from discord import app_commands

NOT_OWNER = "Only the bot owner can use this command."


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
        raise NotImplementedError

    @reload.autocomplete("plugin")
    async def plugin_names(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest the loaded plugins whose name contains ``current``."""
        raise NotImplementedError
