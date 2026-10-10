"""The feedback form: the command, the star buttons and the feedback modal.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:23-161
"""

import logging
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import discord
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import MemberLike, actor_values, placeholder_values
from xincord.core.templates import render_message, render_modal

from .form import highlight, star_count

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config

logger = logging.getLogger(__name__)

# v3's fields in v3's order, all text, and v3's prefix, so that v3's forms keep working.
IDS = ComponentIds(
    "feedbacker",
    ("action", "user_id", "star_count", "submit_channel_id"),
    legacy_prefix="feedbacker@",
)


class FormError(Exception):
    """A form cannot be posted; the message says why, for the log."""


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


class Feedbacker(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.config = config
        self.lang = lang
        self.templates = templates

    async def create_form(
        self,
        interaction: discord.Interaction,
        member: discord.Member | discord.User,
        submit_channel: app_commands.AppCommandChannel,
    ) -> None:
        """Post the form that asks ``member`` to rate the service, for an administrator.

        As in v3, the form goes to the command's channel in the administrator's locale, and the
        response that the command tree deferred says whether it was posted. Where v3 left that
        response "thinking", it says ``form_failure`` and the log says why.
        """
        if not interaction.permissions.administrator:
            await interaction.edit_original_response(content=self.config.form_no_permission)
            return
        try:
            await self._post_form(interaction, member, submit_channel)
        except FormError as error:
            logger.warning(
                "Feedbacker cannot post a form in %s: %s", _name(interaction.guild), error
            )
            await interaction.edit_original_response(content=self.config.form_failure)
            return
        await interaction.edit_original_response(content=self.config.form_success)

    async def _post_form(
        self,
        interaction: discord.Interaction,
        member: discord.Member | discord.User,
        submit_channel: app_commands.AppCommandChannel,
    ) -> None:
        """Post ``ask-message`` with ``member``'s values in the command's channel.

        Raises:
            FormError: The submit channel is not a text channel, ``member`` is not in the guild,
                or the command's channel takes no messages or refused the form.
        """
        if submit_channel.type != discord.ChannelType.text:
            msg = f"the submit channel {_name(submit_channel)} is not a text channel"
            raise FormError(msg)
        # Discord resolves a member only for users in the guild; v3's asMember!! threw here.
        if not isinstance(member, MemberLike):
            msg = f"{_name(member)} is not a member of the guild"
            raise FormError(msg)
        channel = _postable(interaction.channel)
        if channel is None:
            msg = f"the channel {_name(interaction.channel)} takes no messages"
            raise FormError(msg)
        bot = interaction.client.user
        # v3's Placeholder.get(member) for the rated member.
        values = ({} if bot is None else actor_values(member, bot)) | {
            "fb_submit_channel_id": str(submit_channel.id)
        }
        template = self.templates.message("ask-message", interaction.locale.value)
        message = render_message(template, values, build_id=IDS.build)
        try:
            await channel.send(
                content=message.content or None,
                embeds=message.embeds,
                view=message.view,
                files=message.files,
            )
        except discord.HTTPException as error:
            msg = f"the channel {_name(interaction.channel)} refused it: {error}"
            raise FormError(msg) from error

    async def press_star(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Open the feedback modal for the rated member, then highlight the pressed star.

        Anyone else gets ``form_not_you``. As in v3, the modal is rendered in the member's locale
        with the press's values and the star count and the submit channel of the button's ID.
        """
        if fields["user_id"] != str(interaction.user.id):
            await interaction.response.send_message(self.config.form_not_you, ephemeral=True)
            return
        count = fields["star_count"]
        star_count(count)  # a bad count fails now, not after the member typed a feedback
        values = placeholder_values(interaction) | {
            "fb_star_count": count,
            "fb_submit_channel_id": fields["submit_channel_id"],
        }
        template = self.templates.modal("fill-form", interaction.locale.value)
        await interaction.response.send_modal(render_modal(template, values, build_id=IDS.build))
        await _highlight(interaction)

    async def submit_form(
        self, interaction: discord.Interaction, fields: Mapping[str, str]
    ) -> None:
        """Post the submitted feedback in the submit channel, then delete the form."""
        raise NotImplementedError


async def _highlight(interaction: discord.Interaction) -> None:
    """Edit the pressed form so that its pressed star stands out; a refusal is logged.

    v3 queued this edit on the interaction's hook before the modal acknowledged the press, which
    Discord may refuse; the bot edits its own message instead, after the modal opened.
    """
    message = cast("discord.Message", interaction.message)  # every component interaction has one
    pressed = str(cast("Mapping[str, object]", interaction.data or {}).get("custom_id", ""))
    try:
        await message.edit(view=highlight(message, pressed))
    except discord.HTTPException as error:
        logger.warning(
            "Feedbacker cannot highlight the pressed star on message %s: %s", message.id, error
        )


def _postable(channel: object) -> Postable | None:
    """``channel`` if it takes messages, typed by the call that the plugin makes.

    discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union.
    """
    return channel if isinstance(channel, Postable) else None


def _name(entity: object) -> str:
    """The name and the ID of a guild, a channel or a user, for the log."""
    return f"{getattr(entity, 'name', None)} ({getattr(entity, 'id', None)})"
