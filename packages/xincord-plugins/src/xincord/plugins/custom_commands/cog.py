"""The five payment commands and their messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/SimpleCommand.kt:8-58
"""

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.placeholders import global_values
from xincord.core.templates import render_message

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xincord.core.i18n import Lang
    from xincord.core.templates import Message, Templates

logger = logging.getLogger(__name__)

# v3's commands, in v3's order; each one posts the message template of the same name.
COMMANDS = ("cub-none-card", "tsib-none-card", "ctcb-none-card", "ctcb-remit", "chpytwtp-remit")
DESCRIPTION = "generate message"  # v3's description of every command


@runtime_checkable
class Postable(Protocol):
    """A channel that takes messages (forums and categories do not), as the plugin calls it."""

    async def send(
        self,
        *,
        content: str | None = None,
        embeds: Sequence[discord.Embed] = (),
        view: discord.ui.View | discord.ui.LayoutView | None = None,
        files: Sequence[discord.File] = (),
    ) -> object:
        """Send a message to the channel."""
        ...


class CustomCommands(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.lang = lang
        self.templates = templates

    def command(self, name: str) -> app_commands.Command[Any, ..., None]:
        """Build the guild command ``name``, localized from ``register.yaml``.

        As in v3, only administrators see it by default; Discord enforces that, and a guild's
        administrators can change it in the server's integration settings.
        """
        lang = self.lang
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command(name, f"{name}.name"),
            description=lang.command(DESCRIPTION, f"{name}.description"),
            callback=self.post_message,
        )
        return app_commands.default_permissions(administrator=True)(command)

    async def post_message(self, interaction: discord.Interaction) -> None:
        """Post the message named after the command in its channel, then delete the response.

        The message is public, so it is rendered in the default locale for every user, as in v3,
        with v3's global placeholders. When the channel takes no messages or refuses this one, the
        deferred response shows the message instead; v3 had already deleted it.
        """
        name = interaction.command.name if interaction.command else ""
        template = self.templates.message(name, self.lang.default_locale)
        values = global_values(interaction.client)
        channel = _postable(interaction.channel)
        if channel is None:
            logger.warning(
                "CustomCommands cannot post %s in %r, which takes no messages, so it shows it "
                "privately",
                name,
                interaction.channel,
            )
        elif await _send(channel, name, render_message(template, values)):
            await interaction.delete_original_response()
            return
        # Rendered again: discord.py closes a message's files once it sent them, even when Discord
        # refused the message.
        reply = render_message(template, values)
        await interaction.edit_original_response(
            content=reply.content or None,
            embeds=reply.embeds,
            view=reply.view,
            attachments=reply.files,
        )


def _postable(channel: object) -> Postable | None:
    """``channel`` if it takes messages, typed by the call the plugin makes.

    discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union.
    """
    return channel if isinstance(channel, Postable) else None


async def _send(channel: Postable, name: str, message: Message) -> bool:
    """Send the whole ``message`` to ``channel``, as v3 did; return whether Discord took it."""
    try:
        await channel.send(
            content=message.content or None,
            embeds=message.embeds,
            view=message.view,
            files=message.files,
        )
    except discord.HTTPException as error:
        logger.warning(
            "CustomCommands cannot post %s in %r, so it shows it privately: %s",
            name,
            channel,
            error,
        )
        return False
    return True
