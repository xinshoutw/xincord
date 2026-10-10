"""The /bot-info command and its reply.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/BotInfo.kt:10-37
"""

from typing import TYPE_CHECKING, Protocol

from discord.ext import commands

from xincord.core.templates import render_message

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
        """Turn the deferred response into the ``bot-info`` embed, with the counts as they are now.

        v3 wrote the counts into the placeholders that every plugin shared; here they belong to
        this render only.
        """
        guild_count, member_count = counts(interaction.client.guilds)
        values = _bot_values(interaction) | {
            "guild_counts": str(guild_count),
            "member_counts": str(member_count),
            "source_url": self.config.source_url,
        }
        message = self.templates.message("bot-info", interaction.locale.value)
        reply = render_message(message, values)
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=reply.content, embeds=reply.embeds, view=reply.view
        )


def counts(guilds: Collection[Counted]) -> tuple[int, int]:
    """Return the number of ``guilds`` and the sum of their member counts.

    As in v3, a user in several guilds counts once per guild, and bots count. An unknown member
    count (a guild unavailable since the bot connected) adds nothing.
    """
    return len(guilds), sum(guild.member_count or 0 for guild in guilds)


def _bot_values(interaction: discord.Interaction) -> dict[str, str]:
    """v3's global placeholders, the only ones its ``bot-info`` template had: the bot's keys."""
    bot = interaction.client.user  # set once the bot has logged in
    return {} if bot is None else {"bot_id": str(bot.id), "bot_name": bot.name}
