"""The /bot-info command and its reply.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/BotInfo.kt:10-37
"""

from typing import TYPE_CHECKING, Protocol

from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Collection

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


def counts(guilds: Collection[Counted]) -> tuple[int, int]:
    """Stub until the counts exist."""
    raise NotImplementedError
