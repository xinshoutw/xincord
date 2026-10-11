"""The /bot-info command and its reply."""

from typing import TYPE_CHECKING, Any, Protocol

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.placeholders import global_values
from xincord.core.templates import render_message

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

    def command(self) -> app_commands.Command[Any, ..., None]:
        """Build the global ``/bot-info``, localized from ``register.yaml``.

        v3's command had JDA's defaults: usable in guilds and in the bot's DMs, and installed with
        guilds. discord.py sends no contexts or install types unless they are set, which would
        leave them to Discord, so the command sets JDA's.
        """
        lang = self.lang
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("bot-info", "bot-info.name"),
            description=lang.command("show about the bot data", "bot-info.description"),
            callback=self.bot_info,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=False
            ),
            allowed_installs=app_commands.AppInstallationType(guild=True, user=False),
            extras={"global": True},  # v3's globalCommands()
        )
        return command

    async def bot_info(self, interaction: discord.Interaction) -> None:
        """Turn the deferred response into the ``bot-info`` embed, with the counts as they are now.

        v3 wrote the counts into the placeholders that every plugin shared; here they belong to
        this render only.
        """
        guild_count, member_count = counts(interaction.client.guilds)
        values = global_values(interaction.client) | {
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
