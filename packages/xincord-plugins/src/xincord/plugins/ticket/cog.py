"""The commands, the builder, the panels, the ticket channels and their control row.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:56-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:17-332
"""

import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

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
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .model import Draft

logger = logging.getLogger(__name__)

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
        """Edit the deferred response into the builder of a button for message ``message_id``."""
        raise NotImplementedError

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
