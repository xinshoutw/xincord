"""The commands, the builder, the panels, the ticket channels and their control row.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:56-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:17-332
"""

import logging
import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import global_values
from xincord.core.templates import render_message

from .drafts import defaults
from .texts import Texts
from .views import preview_button, preview_embed

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .model import Draft

logger = logging.getLogger(__name__)

BUTTON = 2  # the component type of a button, which v3's onButtonInteraction took
# The component types of user, role, mentionable and channel selects: v3's
# EntitySelectInteractionEvent.
ENTITY_SELECTS = frozenset((5, 6, 7, 8))
# The builder's buttons that open a modal, and the modal's template.
MODALS = {
    "modify-author": "modify-author",
    "modify-content": "modify-content",
    "modify-color": "modify-embed-color",
    "modify-btn-text": "modify-btn-text",
    "modify-reason": "modify-reason-title",
    "prev": "preview-reason",
}
# The builder's buttons that show another screen, and its template (None: the main screen).
SCREENS: dict[str, str | None] = {
    "modify-category": "modify-category",
    "modify-admin": "modify-admin-role",
    "modify-btn-color": "modify-btn-color",
    "back": None,
}
MESSAGE_ID = re.compile(r"[0-9]{1,20}")  # a snowflake as /add-ticket's text option gives it
ROW_SIZE = 5  # the components an action row holds at most


@runtime_checkable
class Fetching(Protocol):
    """A channel that fetches its messages, as v3's ``retrieveMessageById``."""

    async def fetch_message(self, message_id: int, /) -> discord.Message:
        """The channel's message ``message_id``."""
        ...


# v3's fields in v3's order, the user ID in hex as v3 wrote it, and v3's prefix, so that v3's
# panels and ticket channels keep working.
IDS = ComponentIds(
    "ticket",
    ("action", "sub_action", "color_index", "user_id", "msg_id", "btn_index"),
    legacy_prefix="ticket@",
    legacy_hex=("user_id",),
)


@dataclass(frozen=True)
class Target:
    """The message that ``/add-ticket`` adds a button to, and its first embed for the preview."""

    message_id: int
    embed: discord.Embed


@dataclass(frozen=True)
class Session:
    """A user's draft in a guild, the builder message that shows it, and the message it adds to."""

    message_id: int
    draft: Draft
    target: Target | None = None


class Ticket(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates
        # Each user's draft per guild, by user ID and guild ID; v3's StepManager.steps, per user.
        self.drafts: dict[tuple[int, int], Session] = {}

    def commands(self) -> tuple[app_commands.Command[Any, ..., None], ...]:
        """Build v3's ``/create-ticket`` and ``/add-ticket``, localized from ``register.yaml``.

        Guild commands that only administrators see by default, as in v3.
        """
        lang = self.lang
        create: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("create-ticket", "create_ticket.name"),
            description=lang.command("create custom reason of ticket", "create_ticket.description"),
            callback=self.create_ticket,
        )
        add: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("add-ticket", "add_ticket.name"),
            description=lang.command(
                "create custom reason of ticket in the text-channel", "add_ticket.description"
            ),
            callback=self.add_ticket,
        )
        option = "add_ticket.options.message_id"
        app_commands.rename(message_id=lang.command("message_id", f"{option}.name"))(add)
        app_commands.describe(
            message_id=lang.command("for adding extra button", f"{option}.description")
        )(add)
        return tuple(
            app_commands.default_permissions(administrator=True)(command)
            for command in (create, add)
        )

    async def create_ticket(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the builder of a new panel for the user.

        v3's defaults in the user's language; the draft replaces one the user had in the guild,
        and only the new builder message drives it. The command tree deferred the response
        ephemerally, as v3's core did.
        """
        guild_id = interaction.guild_id
        if guild_id is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        await self._open(interaction, guild_id, Session(0, defaults(self.texts(interaction))))

    async def add_ticket(self, interaction: discord.Interaction, message_id: str) -> None:
        """Edit the deferred response into the builder of a button for message ``message_id``.

        The message is looked for in the command's channel, as v3. It must be the bot's (v3 failed
        silently at the confirmation), with a first row that takes a button (v3 compared its size
        with five only, B16) and an embed (v3 stayed "thinking", B9); a text that is no ID (v3
        stayed "thinking", B7) and an unknown message (v3 also stored a broken draft, B8) are
        answered too.
        """
        guild_id = interaction.guild_id
        if guild_id is None:  # guild commands run in guilds only
            return
        texts = self.texts(interaction)
        found = await self._target(interaction, message_id.strip(), texts)
        if isinstance(found, str):
            await interaction.edit_original_response(content=found)
            return
        await self._open(interaction, guild_id, Session(0, defaults(texts), found))

    async def _target(
        self, interaction: discord.Interaction, text: str, texts: Texts
    ) -> Target | str:
        """The message that ``/add-ticket`` names, or the error that answers the command."""
        if not MESSAGE_ID.fullmatch(text):
            return texts.get("error.invalid-message-id", {"tt@message-id": text})
        message = await _fetch(interaction.channel, int(text))
        if message is None:
            return texts.get("error.message-not-found", {"tt@message-id": text})
        refused = _refusal(message, interaction.client.user)
        if refused is not None:
            return texts.get(refused)
        return Target(message.id, message.embeds[0])

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Send a press, a selection or a submission to its handler; ``setup`` routes here.

        As v3's ``onButtonInteraction``, ``onEntitySelectInteraction`` and ``onModalInteraction``:
        the action ``create`` drives the builder; the panel's and the control row's buttons, the
        save select and the reason modal have their own. Anything else, string selects included,
        gets no response.
        """
        fields = parsed.fields
        action = fields.get("action")
        sub_action = fields.get("sub_action", "")
        data = cast("Mapping[str, object]", interaction.data or {})
        if interaction.type is discord.InteractionType.component:
            kind = data.get("component_type")
            if kind == BUTTON and action == "create":
                await self.press(interaction, sub_action, fields)
            elif kind in ENTITY_SELECTS and action == "create":
                await self.choose(interaction, sub_action, _values(data))
        elif interaction.type is discord.InteractionType.modal_submit and action == "create":
            await self.submit(interaction, sub_action)

    async def press(
        self, interaction: discord.Interaction, sub_action: str, fields: Mapping[str, str]
    ) -> None:
        """Handle a press of the builder's button ``sub_action``.

        Without the user's draft, or from a builder message other than the one that shows it, the
        user gets the session-expired text (v3 acknowledged silently, and any builder of the user
        drove the newest step). Unknown sub-actions get no response, as in v3.
        """
        session = self._session(interaction)
        if session is None:
            await _tell(interaction, self.texts(interaction).get("error.expired"))
            return
        if sub_action == "confirm-create":
            await self._confirm(interaction, session)
        elif sub_action == "modify-btn-color-submit":
            await self._style(interaction, session, fields.get("color_index", ""))
        elif sub_action in MODALS:
            await self._open_modal(interaction, session, sub_action)
        elif sub_action in SCREENS:
            await self._screen(interaction, session, SCREENS[sub_action])

    async def choose(
        self, interaction: discord.Interaction, sub_action: str, values: Sequence[str]
    ) -> None:
        """Handle a selection in the builder's select ``sub_action``, as a press."""
        session = self._session(interaction)
        if session is None:
            await _tell(interaction, self.texts(interaction).get("error.expired"))
            return
        await self._select(interaction, session, sub_action, values)

    async def submit(self, interaction: discord.Interaction, sub_action: str) -> None:
        """Handle a submission of the builder's modal ``sub_action``, as a press."""
        session = self._session(interaction)
        if session is None:
            await _tell(interaction, self.texts(interaction).get("error.expired"))
            return
        await self._apply(interaction, session, sub_action)

    async def _open_modal(
        self, interaction: discord.Interaction, session: Session, sub_action: str
    ) -> None:
        """Open the modal of the builder's button ``sub_action``, pre-filled with the draft."""
        raise NotImplementedError

    async def _screen(
        self, interaction: discord.Interaction, session: Session, screen: str | None
    ) -> None:
        """Show the builder's ``screen``, or its main screen."""
        raise NotImplementedError

    async def _style(self, interaction: discord.Interaction, session: Session, index: str) -> None:
        """Set the panel button's style from a color button's index."""
        raise NotImplementedError

    async def _select(
        self,
        interaction: discord.Interaction,
        session: Session,
        sub_action: str,
        values: Sequence[str],
    ) -> None:
        """Change the draft with a selection in the builder's select ``sub_action``."""
        raise NotImplementedError

    async def _apply(
        self, interaction: discord.Interaction, session: Session, sub_action: str
    ) -> None:
        """Change the draft with the submitted modal ``sub_action``."""
        raise NotImplementedError

    async def _confirm(self, interaction: discord.Interaction, session: Session) -> None:
        """Post the panel, or add its button to the message, and store it."""
        raise NotImplementedError

    def _session(self, interaction: discord.Interaction) -> Session | None:
        """The user's draft in the guild, if the interaction comes from the builder showing it."""
        guild_id = interaction.guild_id
        session = None if guild_id is None else self.drafts.get((interaction.user.id, guild_id))
        message = interaction.message
        if session is None or message is None or message.id != session.message_id:
            return None
        return session

    async def _open(
        self, interaction: discord.Interaction, guild_id: int, session: Session
    ) -> None:
        """Show the builder in the deferred response and keep the session with its message."""
        message = self._builder(interaction, session)
        shown = await interaction.edit_original_response(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )
        self.drafts[interaction.user.id, guild_id] = replace(session, message_id=shown.id)

    def _builder(
        self, interaction: discord.Interaction, session: Session, screen: str | None = None
    ) -> Message:
        """The builder's ``screen`` (its main screen by default) in the user's locale.

        v3's templates with its models: the preview embed (the target's first embed for an added
        button) and the preview button; v3 rendered them without a substitutor: its global values.
        """
        target = session.target
        main = "create-ticket" if target is None else "add-ticket"
        embed = preview_embed(session.draft) if target is None else target.embed
        return render_message(
            self.templates.message(screen or main, interaction.locale.value),
            global_values(interaction.client),
            build_id=IDS.build,
            models={
                "tt@embed-demo": embed,
                "tt@btn-demo": preview_button(session.draft, IDS.build),
            },
        )

    def texts(self, interaction: discord.Interaction) -> Texts:
        """The texts of a reply to the user who acted: their locale, else zh-TW (v3's templates).

        ``Lang.text`` falls back per key to zh-TW, which v3 showed every locale without lang files:
        its templates fell back to zh-TW and its texts were Chinese.
        """
        return Texts(self.lang, interaction.locale.value)

    @property
    def public(self) -> Texts:
        """The texts of public messages (the control row, the archive's markers): zh-TW, as v3."""
        return Texts(self.lang, self.lang.default_locale)


async def _tell(interaction: discord.Interaction, text: str) -> None:
    """Answer the interaction with ``text``, ephemerally, as v3's replies."""
    await interaction.response.send_message(text, ephemeral=True)


def _values(data: Mapping[str, object]) -> list[str]:
    """A select's chosen values, snowflakes as text for entity selects."""
    values = data.get("values")
    return (
        [str(value) for value in cast("list[object]", values)] if isinstance(values, list) else []
    )


async def _fetch(channel: object, message_id: int) -> discord.Message | None:
    """The channel's message ``message_id``, or None when Discord has none for the bot there."""
    if not isinstance(channel, Fetching):  # a channel without messages has no such message
        return None
    try:
        return await channel.fetch_message(message_id)
    except discord.HTTPException:
        return None


def _refusal(message: discord.Message, bot: discord.ClientUser | None) -> str | None:
    """The error key when ``/add-ticket`` cannot add a button to ``message``, else None."""
    if bot is None or message.author.id != bot.id:
        return "error.not-own-message"
    if is_full(message):
        return "error.message-full"
    if not message.embeds:
        return "error.no-embed"
    return None


def is_full(message: discord.Message) -> bool:
    """Whether the message's first action row takes no more button: five components, or a select
    (which fills its row).
    """
    row = first_row(message)
    if row is None:
        return False
    children = row.children
    return len(children) >= ROW_SIZE or not all(
        isinstance(child, discord.Button) for child in children
    )


def first_row(message: discord.Message) -> discord.ActionRow | None:
    """The message's first action row, v3's ``firstOrNull { it.type == ACTION_ROW }``."""
    return next(
        (component for component in message.components if isinstance(component, discord.ActionRow)),
        None,
    )
