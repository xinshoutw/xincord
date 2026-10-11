"""AutoRole: members who join a configured guild get that guild's roles."""

from typing import TYPE_CHECKING

import discord

from .cog import AutoRole
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Member joins need the privileged members intent.
INTENTS = discord.Intents(members=True)


async def setup(bot: Bot) -> None:
    """Load the config and add the cog.

    The plugin has no lang files: it has no text.
    """
    context = bot.plugin_context(__name__)
    await bot.add_cog(AutoRole(bot, context.config(Config)))
