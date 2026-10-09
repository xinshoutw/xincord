"""The command tree: ephemeral auto-defer, command scopes, and uploads only when commands change.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-41
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:18-36
"""

from typing import TYPE_CHECKING, Any, override

import discord
from discord import app_commands

if TYPE_CHECKING:
    from xincord.core.storage import Store

type Payload = dict[str, Any]


class CommandTree(app_commands.CommandTree[discord.Client]):
    """discord.py's command tree with v3's ephemeral defer and change-based uploads."""

    @override
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        """Defer application commands ephemerally unless they set ``extras["defer"]`` to False."""
        command = interaction.command
        if (
            interaction.type is discord.InteractionType.application_command
            and command is not None
            and command.extras.get("defer", True)
        ):
            await interaction.response.defer(ephemeral=True, thinking=True)
        return True

    async def payloads(self) -> tuple[list[Payload], list[Payload]]:
        """Return the payloads of the global commands and of the guild commands, translated."""
        raise NotImplementedError

    async def sync_global(self, store: Store, *, force: bool = False) -> bool:
        """Upload the global commands if they changed since the last upload, or if forced.

        Returns:
            Whether they were uploaded. A failed upload is logged and returns False.
        """
        raise NotImplementedError

    async def sync_guild(self, store: Store, guild_id: int, *, force: bool = False) -> bool:
        """Upload the guild commands to ``guild_id`` if they changed there, or if forced.

        Returns:
            Whether they were uploaded. A failed upload is logged and returns False.
        """
        raise NotImplementedError
