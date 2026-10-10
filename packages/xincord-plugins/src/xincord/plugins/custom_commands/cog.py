"""The commands of the config and their messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/SimpleCommand.kt:8-58
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/Register.kt:39-60
"""

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.i18n import localized
from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from xincord.core.i18n import Lang
    from xincord.core.templates import Message, MessageTemplate, Templates

    from .config import CommandSpec, Config

logger = logging.getLogger(__name__)


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

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded; the config's commands by name, for the callback."""
        self.config = config
        self.specs = {spec.name: spec for spec in config.commands}
        self.lang = lang
        self.templates = templates

    def command(self, spec: CommandSpec) -> app_commands.Command[Any, ..., None]:
        """Build the guild command of the config's entry ``spec``, localized from the entry.

        Only members with the entry's permissions see it by default (administrators, as in v3,
        unless the entry says otherwise); Discord enforces that, and a guild's administrators can
        change it in the server's integration settings. An entry that lists guilds is uploaded
        to those guilds only. The command tree defers the command ephemerally unless it replies
        publicly: an ephemeral deferral cannot turn into a public reply.
        """
        names = {key: value.name for key, value in spec.localizations.items() if value.name}
        descriptions = {
            key: value.description for key, value in spec.localizations.items() if value.description
        }
        extras: dict[str, object] = {}
        if spec.guilds:
            extras["guilds"] = frozenset(spec.guilds)
        if spec.reply == "public":
            extras["defer"] = False
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=localized(spec.name, names),
            description=localized(spec.description, descriptions),
            callback=self.post_message,
            extras=extras,
        )
        command.default_permissions = _permissions(spec.permissions)
        return command

    async def post_message(self, interaction: discord.Interaction) -> None:
        """Answer with the command's message template, where the command's entry says.

        ``channel``, v3's way: post the message in the command's channel, then delete the deferred
        response; when the channel takes no messages or refuses this one, the deferred response
        shows the message instead (v3 had already deleted it). ``public``: defer publicly, since
        the command tree left it alone, and edit that response into the message. ``ephemeral``:
        edit the tree's ephemeral deferred response into it. Posts and public replies are rendered
        in the default locale for every user, as v3's posts; an ephemeral reply in the user's. The
        placeholders are the user's, the bot's and the interaction's (v3's, the bot's, among them).
        """
        name = interaction.command.name if interaction.command else ""
        spec = self.specs[name]
        if spec.reply == "public":
            await interaction.response.defer(thinking=True)
        locale = interaction.locale.value if spec.reply == "ephemeral" else self.lang.default_locale
        template = self.templates.message(spec.template_name, locale)
        values = placeholder_values(interaction)
        if spec.reply == "channel" and await _post(interaction.channel, name, template, values):
            await interaction.delete_original_response()
            return
        # Rendered again after a refused post: discord.py closes a message's files once it sent
        # them, even when Discord refused the message.
        reply = render_message(template, values)
        await interaction.edit_original_response(
            content=reply.content or None,
            embeds=reply.embeds,
            view=reply.view,
            attachments=reply.files,
        )


def _permissions(names: Iterable[str]) -> discord.Permissions | None:
    """The default member permissions of discord.py's permission ``names``; None for none."""
    value = 0
    for name in names:
        value |= discord.Permissions.VALID_FLAGS[name]
    return discord.Permissions(value) if value else None


async def _post(
    channel: object, name: str, template: MessageTemplate, values: Mapping[str, str]
) -> bool:
    """Post the message of command ``name`` in ``channel``; return whether Discord took it."""
    postable = _postable(channel)
    if postable is None:
        logger.warning(
            "CustomCommands cannot post %s in %r, which takes no messages, so it shows it "
            "privately",
            name,
            channel,
        )
        return False
    return await _send(postable, name, render_message(template, values))


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
