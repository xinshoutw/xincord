"""The listeners that give members who join a configured guild its roles.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/AutoRole.kt:8-25
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/Event.kt:28-31
"""

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Iterable

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
        """Give a member who joined a configured guild that guild's roles, one by one.

        discord.py builds the member from the join event, so no member cache is needed.
        """
        role_ids = self.roles.get(member.guild.id)
        if role_ids is None or not _can_manage_roles(member.guild):
            return
        for role in _givable(member.guild, role_ids):
            try:
                # discord.py's atomic add sends one add-role request, which keeps the member's
                # other roles; v3's single request replaced them all.
                await member.add_roles(role)
            except discord.HTTPException:
                _skip()


def _can_manage_roles(guild: discord.Guild) -> bool:
    """Whether the bot has Manage Roles in ``guild``."""
    if guild.me.guild_permissions.manage_roles:
        return True
    _skip()
    return False


def _givable(guild: discord.Guild, role_ids: Iterable[int]) -> list[discord.Role]:
    """Return the roles of ``role_ids`` that the bot can give in ``guild``, each once.

    Roles are looked up in ``guild`` at each call: v3 searched every guild, once.
    """
    roles: list[discord.Role] = []
    for role_id in dict.fromkeys(role_ids):
        role = guild.get_role(role_id)
        if role is None or not role.is_assignable():
            _skip()
        else:
            roles.append(role)
    return roles


def _skip() -> None:
    """Stub until the roles that cannot be given are logged."""
    raise NotImplementedError
