"""The listeners that give members who join a configured guild its roles.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/AutoRole.kt:8-25
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/Event.kt:28-31
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    import discord

    from .config import Config


class AutoRole(commands.Cog):
    """The plugin's state and listeners; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config) -> None:
        """Keep the bot and each configured guild's role IDs.

        A reload builds a new cog, so the guilds and their roles change together (v3 replaced
        them one after the other).
        """
        self.bot = bot
        self.roles = config.roles_by_guild()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Stub until members who join get the guild's roles."""
        raise NotImplementedError
