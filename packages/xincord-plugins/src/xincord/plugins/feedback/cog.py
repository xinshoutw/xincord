"""The feedback form: the command, the star buttons and the feedback modal."""

import logging
from typing import TYPE_CHECKING, Any, Protocol, cast, override, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import MemberLike, actor_values, placeholder_values
from xincord.core.templates import modal_values, render_message, render_modal

from .form import highlight, star_count, stars

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.templates import Message, Templates

    from .config import Config

logger = logging.getLogger(__name__)

# The legacy fields in their order, all text, and the legacy prefix: legacy forms keep working.
IDS = ComponentIds(
    "feedback",
    ("action", "user_id", "star_count", "submit_channel_id"),
    legacy_prefix="feedbacker@",
)
FEEDBACK = "form"  # the custom ID of the modal's text input


class FormError(Exception):
    """A form or a review cannot be posted; the message says why, for the log."""


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


class TextChannelOption(app_commands.Transformer[discord.Client]):
    """The ``submit-channel`` option: Discord offers text channels only.

    discord.py's ``discord.TextChannel`` annotation would also offer announcement channels and need
    the channel in the cache; this passes on the channel that Discord resolved. WelcomeGoodbye has
    the same transformer for its ``channel`` option.
    """

    @property
    @override
    def type(self) -> discord.AppCommandOptionType:
        """A channel option."""
        return discord.AppCommandOptionType.channel

    @property
    @override
    def channel_types(self) -> list[discord.ChannelType]:
        """Text channels only."""
        return [discord.ChannelType.text]

    @override
    async def transform(self, interaction: discord.Interaction, value: object, /) -> object:
        """Pass on the ``AppCommandChannel`` that Discord resolved."""
        return value


class Feedback(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.config = config
        self.lang = lang
        self.templates = templates

    def command(self) -> app_commands.Command[Any, ..., None]:
        """Build ``/feedback``, localized from ``register.yaml``.

        A guild command that every member sees: ``create_form`` checks Administrator.
        """
        lang = self.lang
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("feedback", "feedback.name"),
            description=lang.command("Create a feedback form for a member", "feedback.description"),
            callback=self.create_form,
        )
        app_commands.rename(
            member=lang.command("member", "feedback.options.member.name"),
            submit_channel=lang.command("submit-channel", "feedback.options.submit-channel.name"),
        )(command)
        return app_commands.describe(
            member=lang.command("Specify the member", "feedback.options.member.description"),
            submit_channel=lang.command(
                "Specify the submit channel", "feedback.options.submit-channel.description"
            ),
        )(command)

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Send a form's star press or submitted modal to its handler; ``setup`` routes here.

        A press is a ``submit_star`` button and a submission a ``submit_form`` modal, in the legacy
        ID format too; anything else gets no response.
        """
        action = parsed.fields.get("action")
        if interaction.type is discord.InteractionType.component and action == "submit_star":
            await self.press_star(interaction, parsed.fields)
        elif interaction.type is discord.InteractionType.modal_submit and action == "submit_form":
            await self.submit_form(interaction, parsed.fields)

    async def create_form(
        self,
        interaction: discord.Interaction,
        member: discord.Member | discord.User,
        submit_channel: app_commands.Transform[app_commands.AppCommandChannel, TextChannelOption],
    ) -> None:
        """Post the form that asks ``member`` to rate the service, for an administrator.

        ``member`` is a user option: discord.py passes the member that Discord resolved, or the
        user when Discord resolved none, where a ``discord.Member`` annotation would fail before
        the callback and leave the response "thinking".

        The form goes to the command's channel in the administrator's locale, and the response that
        the command tree deferred says whether it was posted: on a failure it says ``form_failure``
        and the log says why.
        """
        if not interaction.permissions.administrator:
            await interaction.edit_original_response(content=self.config.form_no_permission)
            return
        try:
            await self._post_form(interaction, member, submit_channel)
        except FormError as error:
            logger.warning("Feedback cannot post a form in %s: %s", _name(interaction.guild), error)
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
        # Discord resolves a member only for users in the guild.
        if not isinstance(member, MemberLike):
            msg = f"{_name(member)} is not a member of the guild"
            raise FormError(msg)
        channel = _postable(interaction.channel)
        if channel is None:
            msg = f"the channel {_name(interaction.channel)} takes no messages"
            raise FormError(msg)
        bot = interaction.client.user
        # The rated member's placeholder values.
        values = ({} if bot is None else actor_values(member, bot)) | {
            "fb_submit_channel_id": str(submit_channel.id)
        }
        template = self.templates.message("ask-message", interaction.locale.value)
        await _send(channel, render_message(template, values, build_id=IDS.build))

    async def press_star(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Open the feedback modal for the rated member, then highlight the pressed star.

        Anyone else gets ``form_not_you``. The modal is rendered in the member's locale
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
        """Post the member's stars and feedback in the submit channel, then delete the form.

        The submission is acknowledged without a message and the review is rendered in the guild's
        locale with the submitter's values; the feedback is shown as typed. The form is deleted
        only once the review is posted: otherwise it stays for another try,
        the member gets ``form_submit_failure`` and the log says why.
        """
        rating = stars(star_count(fields["star_count"]))
        channel_id = int(fields["submit_channel_id"])
        feedback = modal_values(interaction.data).get(FEEDBACK, "")
        await interaction.response.defer()  # the modal closes, nothing is shown
        try:
            await self._post_review(interaction, channel_id, rating, feedback)
        except FormError as error:
            logger.warning(
                "Feedback cannot post the review of %s in %s: %s",
                _name(interaction.user),
                _name(interaction.guild),
                error,
            )
            await interaction.followup.send(self.config.form_submit_failure, ephemeral=True)
            return
        await _delete_form(interaction)

    async def _post_review(
        self, interaction: discord.Interaction, channel_id: int, rating: str, feedback: str
    ) -> None:
        """Post ``print-result`` in the guild's text channel ``channel_id``.

        Raises:
            FormError: The guild has no such text channel, or the channel refused the review.
        """
        channel = _text_channel(interaction.guild, channel_id)
        if channel is None:
            msg = f"channel {channel_id} is not one of its text channels"
            raise FormError(msg)
        bot = interaction.client.user
        # The submitter's placeholder values.
        values = ({} if bot is None else actor_values(interaction.user, bot)) | {
            "fb_stars": rating,
            "fb_content": feedback,
        }
        locale = (interaction.guild_locale or interaction.locale).value
        template = self.templates.message("print-result", locale)
        await _send(channel, render_message(template, values, build_id=IDS.build))


async def _send(channel: Postable, message: Message) -> None:
    """Post the whole rendered message in ``channel``.

    Raises:
        FormError: The channel refused it.
    """
    try:
        await channel.send(
            content=message.content or None,
            embeds=message.embeds,
            view=message.view,
            files=message.files,
        )
    except discord.HTTPException as error:
        msg = f"the channel {_name(channel)} refused it: {error}"
        raise FormError(msg) from error


async def _highlight(interaction: discord.Interaction) -> None:
    """Edit the pressed form so that its pressed star stands out; a refusal is logged.

    The bot edits its own message after the modal opened: an edit through the interaction
    before the modal acknowledged the press could be refused.
    """
    message = cast("discord.Message", interaction.message)  # every component interaction has one
    pressed = str(cast("Mapping[str, object]", interaction.data or {}).get("custom_id", ""))
    try:
        await message.edit(view=highlight(message, pressed))
    except discord.HTTPException as error:
        logger.warning(
            "Feedback cannot highlight the pressed star on message %s: %s", message.id, error
        )


async def _delete_form(interaction: discord.Interaction) -> None:
    """Delete the form whose review was posted; a failure is logged.

    The second of two submissions from two clients finds the form gone.
    """
    form = cast("discord.Message", interaction.message)  # the modal was opened from the form
    try:
        await form.delete()
    except discord.HTTPException as error:
        logger.warning("Feedback cannot delete form %s after its review: %s", form.id, error)


def _text_channel(guild: discord.Guild | None, channel_id: int) -> Postable | None:
    """The guild's cached text channel ``channel_id``."""
    channel = None if guild is None else guild.get_channel(channel_id)
    is_text = getattr(channel, "type", None) == discord.ChannelType.text
    return _postable(channel) if is_text else None


def _postable(channel: object) -> Postable | None:
    """``channel`` if it takes messages, typed by the call that the plugin makes.

    discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union.
    """
    return channel if isinstance(channel, Postable) else None


def _name(entity: object) -> str:
    """The name and the ID of a guild, a channel or a user, for the log."""
    return f"{getattr(entity, 'name', None)} ({getattr(entity, 'id', None)})"
