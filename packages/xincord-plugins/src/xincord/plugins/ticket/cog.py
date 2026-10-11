"""The commands, the builder, the panels, the ticket channels and their control row."""

import functools
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, cast, override

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.placeholders import global_values, placeholder_values
from xincord.core.templates import modal_values, render_message, render_modal

from .channels import Guild, Postable, cached_channel
from .controls import ControlRow
from .drafts import defaults, select_roles, select_style, submit
from .ids import IDS
from .model import Controls, DataError, hex_color
from .store import Panels
from .targets import fetch, is_full, refusal, unplace
from .texts import Texts, clip, readable_error, tell
from .tickets import can_copy, category_of, opener, overwrites
from .views import control_row, panel_button, preview_button, preview_embed

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .channels import Category, Posted, TicketChannel
    from .model import Draft, Entry
    from .store import Undo

__all__ = ["IDS", "Session", "Target", "Ticket"]

logger = logging.getLogger(__name__)

BUTTON = 2  # the component type of a button, which v3's onButtonInteraction took
# The component types of user, role, mentionable and channel selects: v3's
# EntitySelectInteractionEvent.
ENTITY_SELECTS = frozenset((5, 6, 7, 8))
LOCKS = frozenset(("lock", "unlock"))  # the control row's first button, by its state
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
LABEL_MAX = 45  # Discord's limit of a modal input's label
MESSAGE_ID = re.compile(r"[0-9]{1,20}")  # a snowflake as /add-ticket's text option gives it
# What an error shows of a typed text, in UTF-16 code units: Discord's string options take 6000
# characters, and its replies 2000.
TYPED_MAX = 100
GUILD_ID = re.compile(r"[1-9][0-9]{0,19}")  # a guild ID in decimal, as the store's keys hold it


class PanelError(Exception):
    """A panel cannot be posted or its button added; the message says why, for the user."""


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


class Ticket(ControlRow, commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them.

    The control row's handlers and the texts come from :class:`ControlRow`.
    """

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates
        self.panels = Panels(store)
        # Each user's draft per guild, by user ID and guild ID; v3's StepManager.steps, per user.
        self.drafts: dict[tuple[int, int], Session] = {}
        self.clock = time.time
        self.zone = None  # the host's, as v3's ZoneId.systemDefault()

    @override
    async def cog_load(self) -> None:
        """Forget the left guilds at once when the plugin loads into a ready bot, as on a reload."""
        if self.bot.is_ready():
            await self.forget_left_guilds()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Forget the guilds that the bot left while offline; this fires for each session."""
        await self.forget_left_guilds()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Delete the panels of a guild that the bot left or was removed from, as v3 did, and
        drop its drafts (v3 kept the user's step).

        discord.py does not fire this during an outage (``on_guild_unavailable``).
        """
        await self.panels.forget(guild.id)
        self.drafts = {key: session for key, session in self.drafts.items() if key[1] != guild.id}

    async def forget_left_guilds(self) -> None:
        """Delete the panels of the guilds that the bot is no longer in.

        v3 deleted them only when it saw the bot leave a guild while the plugin was enabled. By
        ``on_ready``, discord.py knows every guild of the session, unavailable ones included. A
        key that is no guild ID (a hand edit; the plugin never writes one) is left, with a warning.
        """
        for key in await self.panels.guild_ids():
            if not GUILD_ID.fullmatch(key):
                logger.warning(
                    "Ticket ignores the panels stored under %r, which is no guild ID", key
                )
            elif self.bot.get_guild(int(key)) is None:
                await self.panels.forget(int(key))
                logger.info("Ticket deleted the panels of guild %s, which the bot left", key)

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
            typed = {"tt@message-id": clip(text, TYPED_MAX)}
            return texts.get("error.invalid-message-id", typed)
        message = await fetch(interaction.channel, int(text))
        if message is None:
            return texts.get("error.message-not-found", {"tt@message-id": text})
        refused = refusal(message, interaction.client.user)
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
        data = cast("Mapping[str, object]", interaction.data or {})
        kind = data.get("component_type")  # None for a modal
        if interaction.type is discord.InteractionType.modal_submit:
            await self._modal(interaction, fields)
        elif kind == BUTTON:
            await self._button(interaction, fields)
        elif kind in ENTITY_SELECTS:
            await self._entity_select(interaction, fields, _values(data))

    async def _modal(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Send a modal's submission to the handler of the ID's action; others get no response."""
        action = fields.get("action")
        if action == "create":
            await self.submit(interaction, fields.get("sub_action", ""))
        elif action == "submit":
            await self.open_ticket(interaction, fields)

    async def _button(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Send a button's press to the handler of the ID's action; others get no response."""
        action = fields.get("action")
        if action == "create":
            await self.press(interaction, fields.get("sub_action", ""), fields)
        elif action == "press":
            await self.ask(interaction, fields)
        elif action in LOCKS:
            await self.lock(interaction, fields, locked=action == "lock")
        elif action == "delete":
            await self.delete(interaction, fields)
        elif action == "save":
            await self.save(interaction, fields)

    async def _entity_select(
        self, interaction: discord.Interaction, fields: Mapping[str, str], values: Sequence[str]
    ) -> None:
        """Send an entity select's choice to the handler of the ID's action; others get no
        response."""
        action = fields.get("action")
        if action == "create":
            await self.choose(interaction, fields.get("sub_action", ""), values)
        elif action == "save":
            await self.select_target(interaction, fields, values)

    async def ask(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Answer a panel button with the reason modal of its stored entry.

        The entry is the one of the ID's message, else the pressed message (v3), at the button's
        index; without one, the user gets v3's not-found text. v3's ``press-ticket`` opens in the
        user's locale, its input labeled with the reason title (clipped to Discord's 45-character
        label) and its ID naming the message that the entry came from (v3 named the pressed
        message even when it had used the ID's).
        """
        message = interaction.message
        message_id = fields.get("msg_id") or (None if message is None else str(message.id))
        index = fields.get("btn_index", "")
        guild_id = interaction.guild_id
        entry = (
            None
            if guild_id is None or message_id is None
            else await self.panels.entry(guild_id, message_id, index)
        )
        if message_id is None or entry is None:
            await tell(interaction, self.texts(interaction).get("error.not-found"))
            return
        values = placeholder_values(interaction) | {
            "tt@msg-id": message_id,
            "tt@btn-index": index,
            "tt@reason": clip(entry.reason_title, LABEL_MAX),
        }
        template = self.templates.modal("press-ticket", interaction.locale.value)
        await interaction.response.send_modal(render_modal(template, values, build_id=IDS.build))

    async def open_ticket(
        self, interaction: discord.Interaction, fields: Mapping[str, str]
    ) -> None:
        """Open a ticket channel for the member who submitted the reason modal.

        Deferred ephemerally (v3's ``deferReply(true)``), then the entry and its category (v3's
        replies after the deferral never arrived, B3, and a missing entry threw, B4), the channel,
        named after the member's username, and its opener; the member is told where to go. A
        refusal answers ``ticket-failed``; a channel whose opener was refused is deleted.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        texts = self.texts(interaction)
        controls = Controls(
            interaction.user.id, fields.get("msg_id", ""), fields.get("btn_index", "")
        )
        guild_id = interaction.guild_id
        entry = (
            None
            if guild_id is None
            else await self.panels.entry(guild_id, controls.message_id, controls.index)
        )
        if entry is None:
            await interaction.edit_original_response(content=texts.get("error.not-found"))
            return
        category = self._category(interaction, entry.category_id)
        if category is None:
            await interaction.edit_original_response(content=texts.get("error.no-category"))
            return
        reason = modal_values(interaction.data).get("reason", "")
        try:
            channel = await self._create(interaction, category, entry)
            await self._send_opener(channel, entry, reason, controls)
        except discord.HTTPException as error:
            logger.warning(
                "Ticket cannot open a ticket for member %s in guild %s: %s",
                interaction.user.id,
                guild_id,
                error,
            )
            failed = texts.get("error.ticket-failed", {"tt@error": readable_error(error)})
            await interaction.edit_original_response(content=failed)
            return
        going = texts.get("reply.go-to-channel", {"tt@channel": channel.mention})
        await interaction.edit_original_response(content=going)

    def _category(self, interaction: discord.Interaction, category_id: int) -> Category | None:
        """The entry's category: the panel channel's for 0, else the guild's cached one."""
        if category_id == 0:
            found = category_of(interaction.channel)
        else:
            guild = cast("object", interaction.guild)
            found = guild.get_channel(category_id) if isinstance(guild, Guild) else None
        if getattr(found, "type", None) is not discord.ChannelType.category:
            return None
        return cast("Category", found)

    async def _create(
        self, interaction: discord.Interaction, category: Category, entry: Entry
    ) -> TicketChannel:
        """Create the ticket's text channel in ``category``, named after the member's username.

        discord.py's ``create_text_channel(overwrites=...)`` does not copy the category's
        overwrites as JDA's did, so the whole map is built.
        """
        guild = cast("discord.Guild", interaction.guild)
        me = guild.me
        copied = {
            target: overwrite
            for target, overwrite in category.overwrites.items()
            # discord.py would send an uncached role's overwrite as a member's
            if not (isinstance(target, discord.Object) and target.type is discord.Role)
        }
        if not can_copy(
            copied.values(),
            category.permissions_for(me),
            administrator=me.guild_permissions.administrator,
        ):
            copied = {}
        roles = [
            role for role_id in entry.admin_ids if (role := guild.get_role(role_id)) is not None
        ]
        built = overwrites(
            copied,
            everyone=cast("object", guild.default_role),
            member=cast("object", interaction.user),
            roles=roles,
            me=cast("object", me),
        )
        return await category.create_text_channel(interaction.user.name, overwrites=built)

    async def _send_opener(
        self, channel: TicketChannel, entry: Entry, reason: str, controls: Controls
    ) -> None:
        """Send v3's opener with the unlocked control row; delete the channel when it is refused.

        The staff roles ping and nothing else does (v3 pinged everything, S1).

        Raises:
            discord.HTTPException: Discord refused a message.
        """
        mentions = discord.AllowedMentions(
            everyone=False, users=False, roles=[discord.Object(role) for role in entry.admin_ids]
        )
        *parts, last = opener(entry.admin_ids, reason)
        row = control_row(controls, locked=False, texts=self.public, build_id=IDS.build)
        try:
            for part in parts:
                await channel.send(content=part, allowed_mentions=mentions)
            await channel.send(content=last, allowed_mentions=mentions, view=row)
        except discord.HTTPException:
            await _delete_channel(channel)
            raise

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
            await tell(interaction, self.texts(interaction).get("error.expired"))
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
            await tell(interaction, self.texts(interaction).get("error.expired"))
            return
        await self._select(interaction, session, sub_action, values)

    async def submit(self, interaction: discord.Interaction, sub_action: str) -> None:
        """Handle a submission of the builder's modal ``sub_action``, as a press."""
        session = self._session(interaction)
        if session is None:
            await tell(interaction, self.texts(interaction).get("error.expired"))
            return
        await self._apply(interaction, session, sub_action)

    async def _open_modal(
        self, interaction: discord.Interaction, session: Session, sub_action: str
    ) -> None:
        """Open the modal of the builder's button ``sub_action``, pre-filled with the draft.

        In the user's locale, with v3's ``Placeholder.get(event)`` and the draft's ``tt@*`` values,
        inserted as written; an empty value leaves its input empty. The preview button opens v3's
        ``preview-reason``, titled with the reason title, which v3 could not reach (B1).
        """
        draft = session.draft
        values = placeholder_values(interaction) | {
            "tt@author": draft.author,
            "tt@author-icon-url": draft.author_icon_url,
            "tt@title": draft.title,
            "tt@description": draft.description,
            "tt@hex-color": hex_color(draft.color),
            "tt@btn-text": draft.button_text,
            "tt@btn-emoji": draft.button_emoji,
            "tt@reason-title": draft.reason_title,
        }
        template = self.templates.modal(MODALS[sub_action], interaction.locale.value)
        await interaction.response.send_modal(render_modal(template, values, build_id=IDS.build))

    async def _screen(
        self, interaction: discord.Interaction, session: Session, screen: str | None = None
    ) -> bool:
        """Show the builder's ``screen``, or its main screen, through the interaction.

        One type-7 response replaces the whole message, v3's ``deferEdit`` and the edit through
        the command's hook, which stopped working after 15 minutes (B14). When Discord refuses it
        (an emoji or a URL it does not take), the interaction is still open: the user gets the
        refused text with Discord's error, and False comes back.
        """
        message = self._builder(interaction, session, screen)
        try:
            await interaction.response.edit_message(
                content=message.content,
                embeds=message.embeds,
                view=message.view,
                attachments=message.files,
            )
        except discord.HTTPException as error:
            reason = {"tt@error": readable_error(error)}
            await tell(interaction, self.texts(interaction).get("error.refused", reason))
            return False
        return True

    async def _style(self, interaction: discord.Interaction, session: Session, index: str) -> None:
        """Set the panel button's style from a color button's index; show the main screen."""
        await self._update(interaction, session, select_style(session.draft, index))

    async def _select(
        self,
        interaction: discord.Interaction,
        session: Session,
        sub_action: str,
        values: Sequence[str],
    ) -> None:
        """Change the draft with a selection in the builder's select ``sub_action``.

        The role select replaces the staff roles; the category select sets the category when the
        guild's cache knows it as a category, else answers v3's error. Others change nothing. Each
        change shows the main screen, as v3.
        """
        draft = session.draft
        if sub_action == "modify-admin":
            draft = select_roles(draft, values)
        elif sub_action == "modify-category":
            chosen = values[0] if values else ""
            if not _is_category(interaction.guild, chosen):
                texts = self.texts(interaction)
                await tell(
                    interaction, texts.get("error.category-not-found", {"tt@category-id": chosen})
                )
                return
            draft = replace(draft, category_id=int(chosen))
        await self._update(interaction, session, draft)

    async def _apply(
        self, interaction: discord.Interaction, session: Session, sub_action: str
    ) -> None:
        """Change the draft with the submitted modal ``sub_action`` and show the main screen.

        An invalid value gets its error ephemerally and leaves the draft. A valid one replaces the
        builder message through the submission (a modal opened from a message may update it),
        where v3 deferred and edited it through the command's 15-minute hook.
        """
        values = modal_values(interaction.data)
        changed = submit(session.draft, sub_action, values)
        if isinstance(changed, str):
            typed = {"tt@color": values.get("color", "")}
            await tell(interaction, self.texts(interaction).get(changed, typed))
            return
        await self._update(interaction, session, changed)

    async def _update(
        self, interaction: discord.Interaction, session: Session, draft: Draft
    ) -> None:
        """Show ``draft`` in the builder's main screen through the interaction, then keep it.

        A draft that Discord refuses to show is not kept: v3 kept it, and every later render of
        the builder failed silently.
        """
        changed = replace(session, draft=draft)
        if await self._screen(interaction, changed):
            # The session was found by the user and this interaction's guild.
            self.drafts[interaction.user.id, cast("int", interaction.guild_id)] = changed

    async def _confirm(self, interaction: discord.Interaction, session: Session) -> None:
        """Post the panel, or add its button to the message, store it and delete the builder.

        The draft is taken before the first await, so a second press meanwhile gets the
        session-expired text. When nothing could be posted or stored, the draft comes back (unless
        the user started another), the builder stays and ``create-failed`` tells the user why; v3
        deleted the builder first and never acknowledged the press, so failures were invisible
        (B15).
        """
        key = (interaction.user.id, cast("int", interaction.guild_id))
        del self.drafts[key]
        try:
            await interaction.response.defer()  # v3's deferEdit: the builder stays for now
            if session.target is None:
                await self._post(interaction, key[1], session.draft)
            else:
                await self._add(interaction, key[1], session.draft, session.target)
        except PanelError as error:
            self.drafts.setdefault(key, session)
            logger.warning(
                "Ticket cannot create a panel in channel %s of guild %s: %s",
                interaction.channel_id,
                key[1],
                error,
            )
            failed = self.texts(interaction).get("error.create-failed", {"tt@error": str(error)})
            await interaction.followup.send(failed, ephemeral=True)
            return
        except BaseException:
            # Discord refused the acknowledgement, or the task was cancelled, before any post.
            self.drafts.setdefault(key, session)
            raise
        await interaction.delete_original_response()

    async def _post(self, interaction: discord.Interaction, guild_id: int, draft: Draft) -> None:
        """Post v3's ``confirm-create`` in the builder's channel and store its button's entry.

        Raises:
            PanelError: The channel takes no messages or refused the panel, or the store failed (the
                panel is then deleted).
        """
        channel = cast("object", interaction.channel)
        if not isinstance(channel, Postable):
            msg = "the channel takes no messages"
            raise PanelError(msg)
        message = render_message(
            self.templates.message("confirm-create", interaction.locale.value),
            global_values(interaction.client),
            build_id=IDS.build,
            models={"tt@embed": preview_embed(draft), "tt@btn": panel_button(draft, 0, IDS.build)},
        )
        try:
            posted = await channel.send(
                content=message.content or None,
                embeds=message.embeds,
                view=message.view,
                files=message.files,
            )
        except discord.HTTPException as error:
            raise PanelError(readable_error(error)) from error
        try:
            await self.panels.add(guild_id, str(posted.id), draft.entry())
        except (DataError, sqlite3.Error) as error:
            await _delete(posted)
            raise PanelError(readable_error(error)) from error

    async def _add(
        self, interaction: discord.Interaction, guild_id: int, draft: Draft, target: Target
    ) -> None:
        """Append the panel's button to the target's first row and store its entry.

        Under the guild's lock, the message is fetched again, so that two confirmations for one
        message never take the same index (v3 edited from its snapshot). The index is the stored
        list's length (v3 used the row's size, B6), and only the view changes: v3 kept the first
        embed and the first row alone (B17) and threw for a message without rows. When the store
        fails, the message gets its earlier view back: a button without its entry would answer
        not-found, and the next confirmation would give a second button its ID.

        Raises:
            PanelError: The message is gone or full, Discord refused the edit, or the store failed.
        """
        texts = self.texts(interaction)
        channel = interaction.channel

        async def place(index: int) -> Undo:
            message = await fetch(channel, target.message_id)
            if message is None:
                missing = {"tt@message-id": str(target.message_id)}
                raise PanelError(texts.get("error.message-not-found", missing))
            if message.flags.components_v2 or is_full(message):
                raise PanelError(texts.get("error.message-full"))
            view = discord.ui.View.from_message(message, timeout=None)
            button = panel_button(draft, index, IDS.build)
            button.row = 0  # the first action row, or a new one
            view.add_item(button)
            view.stop()  # the router handles its buttons, not discord.py
            try:
                await message.edit(view=view)
            except discord.HTTPException as error:
                raise PanelError(readable_error(error)) from error
            # discord.py's edit returns a new message: this one keeps the earlier components.
            return functools.partial(unplace, message)

        try:
            await self.panels.add(guild_id, str(target.message_id), draft.entry(), place)
        except (DataError, sqlite3.Error) as error:
            raise PanelError(readable_error(error)) from error

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


async def _delete_channel(channel: TicketChannel) -> None:
    """Delete a ticket channel whose opener was refused; a failure is logged."""
    try:
        await channel.delete()
    except discord.HTTPException as error:
        logger.warning("Ticket cannot delete the channel %s: %s", channel.id, error)


async def _delete(posted: Posted) -> None:
    """Delete a panel whose entry was not stored; a failure is logged."""
    try:
        await posted.delete()
    except discord.HTTPException as error:
        logger.warning(
            "Ticket cannot delete the panel %s, which it did not store: %s", posted.id, error
        )


def _values(data: Mapping[str, object]) -> list[str]:
    """A select's chosen values, snowflakes as text for entity selects."""
    values = data.get("values")
    return (
        [str(value) for value in cast("list[object]", values)] if isinstance(values, list) else []
    )


def _is_category(guild: object, text: str) -> bool:
    """Whether the guild's cache knows ``text`` as a category's ID, v3's ``getCategoryById``."""
    return getattr(cached_channel(guild, text), "type", None) is discord.ChannelType.category
