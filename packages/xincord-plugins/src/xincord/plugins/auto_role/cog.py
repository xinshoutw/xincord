"""The listeners that give members who join a configured guild its roles."""

import logging
from typing import TYPE_CHECKING, override

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .config import Config

logger = logging.getLogger(__name__)


class AutoRole(commands.Cog):
    """The plugin's state and listeners; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config) -> None:
        """Keep the bot and each configured guild's role IDs.

        A reload builds a new cog, so the guilds and their roles change together (v3 replaced
        them one after the other).
        """
        self.bot = bot
        self.roles = config.roles_by_guild()

    @override
    async def cog_load(self) -> None:
        """Check the config at once when the plugin loads into a ready bot, as on a reload."""
        if self.bot.is_ready():
            self.check()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Check the config once the guilds are known; discord.py fires this per session."""
        self.check()

    def check(self) -> None:
        """Log what keeps each configured guild's roles from being given.

        v3 found these problems only when a member joined, and logged none for unknown role IDs.
        """
        for guild_id, role_ids in self.roles.items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                logger.warning(
                    "AutoRole gives no roles in guild %s: the bot is not in it", guild_id
                )
                continue
            if guild.unavailable:  # an outage: no roles or members are known, and none can join
                continue
            _can_manage_roles(guild)
            _givable(guild, role_ids)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Give a member who joined a configured guild that guild's roles, one by one.

        discord.py builds the member from the join event, so no member cache is needed.
        """
        guild = member.guild
        role_ids = self.roles.get(guild.id)
        if role_ids is None or not _can_manage_roles(guild):
            return
        for role in _givable(guild, role_ids):
            try:
                # discord.py's atomic add sends one add-role request, which keeps the member's
                # other roles; v3's single request replaced them all.
                await member.add_roles(role)
            except discord.HTTPException as error:
                logger.warning(
                    "AutoRole could not give role %s (%s) to %s (%s) in %s (%s): %s",
                    role.name,
                    role.id,
                    member.name,
                    member.id,
                    guild.name,
                    guild.id,
                    error,
                )


def _can_manage_roles(guild: discord.Guild) -> bool:
    """Whether the bot has Manage Roles in ``guild``; log a warning if it does not.

    JDA refused before sending in this case; v3 gave no role then either.
    """
    if guild.me.guild_permissions.manage_roles:
        return True
    logger.warning(
        "AutoRole gives no roles in %s (%s): the bot lacks Manage Roles", guild.name, guild.id
    )
    return False


def _givable(guild: discord.Guild, role_ids: Iterable[int]) -> list[discord.Role]:
    """Return the roles of ``role_ids`` that the bot can give in ``guild``, each once.

    Roles are looked up in ``guild`` at each call: v3 searched every guild, once. Each role that
    is missing or that the bot cannot give is logged and left out; in v3, one such role made JDA
    refuse them all, and missing ones were dropped silently.
    """
    roles: list[discord.Role] = []
    for role_id in dict.fromkeys(role_ids):
        role = guild.get_role(role_id)
        if role is None:
            logger.warning(
                "AutoRole skips role %s: it is not in %s (%s)", role_id, guild.name, guild.id
            )
        elif not role.is_assignable():  # discord.py makes JDA's client-side checks
            logger.warning(
                "AutoRole skips role %s (%s) in %s (%s): it is managed, @everyone or not below "
                "the bot's highest role",
                role.name,
                role.id,
                guild.name,
                guild.id,
            )
        else:
            roles.append(role)
    return roles
