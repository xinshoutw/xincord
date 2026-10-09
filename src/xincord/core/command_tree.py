"""The command tree: ephemeral auto-defer, command scopes, and uploads only when commands change.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-41
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:18-36
"""

from typing import override

import discord
from discord import app_commands


class CommandTree(app_commands.CommandTree[discord.Client]):
    """discord.py's command tree with v3's ephemeral defer and change-based uploads."""

    @override
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        """Defer application commands ephemerally unless they set ``extras["defer"]`` to False."""
        raise NotImplementedError
