"""The /bot-info command and its reply.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/BotInfo.kt:10-37
"""

from typing import TYPE_CHECKING, Protocol

from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Collection

    import discord

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config


class Counted(Protocol):
    """A guild as the counts see it; ``discord.Guild`` is one."""

    @property
    def member_count(self) -> int | None:
        """The guild's member count, or None when Discord has not sent it."""
        ...


class BotInfo(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.config = config
        self.lang = lang
        self.templates = templates

    async def bot_info(self, interaction: discord.Interaction) -> None:
        """Stub until the reply exists."""
        raise NotImplementedError


def counts(guilds: Collection[Counted]) -> tuple[int, int]:
    """Return the number of ``guilds`` and the sum of their member counts.

    As in v3, a user in several guilds counts once per guild, and bots count. An unknown member
    count (a guild unavailable since the bot connected) adds nothing.
    """
    return len(guilds), sum(guild.member_count or 0 for guild in guilds)
