"""UptimeHeartbeat: each configured listener pushes an HTTP GET to its URL at a fixed delay."""

from typing import TYPE_CHECKING

import discord

from .cog import UptimeHeartbeat
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# No gateway events: v3 registered a listener without handlers.
INTENTS = discord.Intents.none()


async def setup(bot: Bot) -> None:
    """Load the config and add the cog.

    The plugin has no lang files: v3 had no text.
    """
    context = bot.plugin_context(__name__)
    await bot.add_cog(UptimeHeartbeat(bot, context.config(Config)))
