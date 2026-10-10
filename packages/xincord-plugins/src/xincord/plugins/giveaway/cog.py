"""The command, the builder, the post's buttons and the automatic draw.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:44-633
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:16-380
"""

import asyncio
import logging
import random
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Protocol, cast, override, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import global_values, placeholder_values
from xincord.core.templates import modal_values, render_message, render_modal

from .drafts import problem, remove_last_prize, submit, switch_policy
from .model import DataError, Draft, Drawer, Instance, draw, join, new_id
from .store import Giveaways
from .texts import Texts, language, post_buttons, post_embed, preview, result
from .times import format_end_time

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .config import Config

logger = logging.getLogger(__name__)

# v3's fields in v3's order, all text, and v3's prefix, so that v3's posts keep working.
IDS = ComponentIds("giveaway", ("action", "sub_action", "giveaway_id"), legacy_prefix="giveaway@")
BUTTON = 2  # the component type of a button, which v3's onButtonInteraction took
# The builder's buttons that open the modal of the same name, and the modals that change a draft.
FIRST_PASS = 5  # v3's initial delay of the automatic draw, in seconds after READY
GUILD_ID = re.compile(r"[0-9]+")  # the store's keys, unless someone edited them

type Sleep = Callable[[float], Awaitable[object]]

# The text of each refusal of a draw or a reroll.
REFUSALS = {
    "not-allowed": "error.not-allowed",
    "already-drawn": "error.drawn",
    "too-early": "error.too-early",
    "not-drawn": "error.not-drawn",
}
MODALS = frozenset(
    ("set-title", "set-description", "set-end-time", "set-sponsor", "set-thumbnail", "add-prize")
)


class PostError(Exception):
    """A giveaway cannot be posted; the message says why, for the user and the log."""


class Posted(Protocol):
    """A message that the bot sent, as the plugin uses it."""

    @property
    def id(self) -> int:
        """The message's ID."""
        ...

    @property
    def jump_url(self) -> str:
        """The message's link."""
        ...

    async def delete(self) -> None:
        """Delete the message."""
        ...


class Editable(Protocol):
    """A message that the bot can edit without fetching it, as the plugin calls it."""

    async def edit(
        self,
        *,
        content: str | None = None,
        embeds: Sequence[discord.Embed] = (),
        view: discord.ui.View | discord.ui.LayoutView | None = None,
        attachments: Sequence[discord.File] = (),
    ) -> object:
        """Replace the message."""
        ...


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
    ) -> Posted:
        """Send a message to the channel."""
        ...


class Channel(Postable, Protocol):
    """A partial messageable: messages can be sent there and edited by ID."""

    def get_partial_message(self, message_id: int, /) -> Editable:
        """The channel's message ``message_id``, without fetching it."""
        ...


@dataclass(frozen=True)
class Session:
    """A user's draft in a guild and the builder message that shows it."""

    message_id: int
    draft: Draft


class Giveaway(commands.Cog):
    """The plugin's state, handlers and loop; ``setup`` registers them."""

    def __init__(
        self, bot: commands.Bot, config: Config, store: Store, lang: Lang, templates: Templates
    ) -> None:
        """Keep the bot, the config, the store and what ``setup`` loaded."""
        self.bot = bot
        self.config = config
        self.store = store
        self.giveaways = Giveaways(store)
        self.lang = lang
        self.templates = templates
        # The winners' draws: the operating system's randomness, never a seeded generator.
        self.random: random.Random = random.SystemRandom()
        # Each user's draft per guild, by user ID and guild ID; v3's StepManager.steps.
        self.drafts: dict[tuple[int, int], Session] = {}
        self.clock: Callable[[], float] = time.time  # now, in epoch seconds
        self.sleep: Sleep = asyncio.sleep  # between the automatic draw's passes
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # the automatic draw once loaded

    @override
    async def cog_load(self) -> None:
        """Start the automatic draw, which waits until the bot is ready.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is drawn before READY; in a ready bot, as after a reload, the first pass comes five seconds
        later, as v3's scheduler started on each load.
        """
        self.tasks = (asyncio.create_task(self._auto_draw(), name="Giveaway automatic draw"),)

    @override
    async def cog_unload(self) -> None:
        """Stop the automatic draw and wait for it, before the store closes."""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Drop the drafts of a guild that the bot left."""
        raise NotImplementedError

    async def _auto_draw(self) -> None:
        """Pass five seconds after READY, then each ``autoDrawIntervalSeconds`` after a pass.

        v3's scheduler ran at a fixed rate from each start; a pass takes milliseconds. A failed
        pass is logged and the next one runs, as v3's ``runCatching``.
        """
        await self.bot.wait_until_ready()
        await self.sleep(FIRST_PASS)
        while True:
            try:
                await self.draw_due()
            except Exception:
                logger.exception("Giveaway's automatic draw failed")
            await self.sleep(self.config.period)

    async def draw_due(self) -> None:
        """One pass of the automatic draw: draw, store and announce the due giveaways.

        Only in guilds that the bot is in and that are available: v3 also drew those of guilds it
        had left while offline, without posting. Each guild's draws are stored before its posts
        are updated and the winners announced; a guild that fails is logged, the others go on.
        """
        now = int(self.clock())
        for key in await self.giveaways.guild_ids():
            guild = self.bot.get_guild(int(key)) if GUILD_ID.fullmatch(key) else None
            if guild is None or guild.unavailable:
                continue
            try:
                drawn = await self.giveaways.draw_due(guild.id, now, self.random)
            except DataError, sqlite3.Error:
                logger.exception("Giveaway cannot draw the due giveaways of guild %s", key)
                continue
            for instance in drawn:
                await self._announce(instance)

    async def _announce(self, instance: Instance) -> None:
        """Update the post of a giveaway drawn automatically and announce its winners there.

        Through a partial messageable, so threads, announcement channels and voice channel chats
        work without the cache; v3 reached text channels only and drew the others silently. Each
        refusal is a warning naming the giveaway.
        """
        partial = self.bot.get_partial_messageable(instance.channel_id, guild_id=instance.guild_id)
        channel = cast("Channel", partial)  # the send and edit overloads take no view union
        post = self.render_post(instance)
        try:
            await channel.get_partial_message(instance.message_id).edit(
                content=post.content,
                embeds=post.embeds,
                view=post.view,
                attachments=post.files,
            )
        except discord.HTTPException as error:
            logger.warning("Giveaway cannot update the post of giveaway %s: %s", instance.id, error)
        texts = self._giveaway_texts(instance)
        message = render_message(
            self.templates.message("auto-draw-result", texts.locale),
            global_values(self.bot) | result(instance, texts, reroll=False),
            build_id=IDS.build,
        )
        try:
            await channel.send(
                content=message.content or None,
                embeds=message.embeds,
                view=message.view,
                files=message.files,
            )
        except discord.HTTPException as error:
            logger.warning(
                "Giveaway cannot announce the winners of giveaway %s: %s", instance.id, error
            )

    def command(self) -> app_commands.Command[Any, ..., None]:
        """Build v3's ``/create-giveaway``, localized from ``register.yaml``.

        A guild command without options that only administrators see by default, as in v3;
        confirming a draft checks Administrator again.
        """
        lang = self.lang
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("create-giveaway", "create_giveaway.name"),
            description=lang.command(
                "Create a giveaway with step-by-step setup", "create_giveaway.description"
            ),
            callback=self.create_giveaway,
        )
        return app_commands.default_permissions(administrator=True)(command)

    async def create_giveaway(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the builder of a new draft for the user.

        The draft replaces one the user had in the guild, as v3's; only the new builder message
        drives it. The command tree deferred the response ephemerally, as v3's core did.
        """
        guild_id = interaction.guild_id
        if guild_id is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        draft = Draft()
        message = self._builder(interaction, draft)
        shown = await interaction.edit_original_response(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )
        self.drafts[interaction.user.id, guild_id] = Session(shown.id, draft)

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Send a press or a submission to its handler; ``setup`` routes here.

        As v3's ``onButtonInteraction`` and ``onModalInteraction``: buttons with the action
        ``create`` drive the builder, and so do modals; ``participate`` joins or leaves a giveaway.
        Anything else, select menus included, gets no response.
        """
        action = parsed.fields.get("action")
        sub_action = parsed.fields.get("sub_action", "")
        data = cast("Mapping[str, object]", interaction.data or {})
        if interaction.type is discord.InteractionType.component:
            if data.get("component_type") != BUTTON:
                return
            if action == "create":
                await self.press(interaction, sub_action)
            elif action == "participate":
                await self.join(interaction, parsed.fields.get("giveaway_id"))
            elif action in {"draw", "reroll"}:
                giveaway_id = parsed.fields.get("giveaway_id")
                await self.draw(interaction, giveaway_id, reroll=action == "reroll")
        elif interaction.type is discord.InteractionType.modal_submit and action == "create":
            await self.submit(interaction, sub_action)

    async def join(self, interaction: discord.Interaction, giveaway_id: str | None) -> None:
        """Add the user to the giveaway's participants, or remove them, as v3's toggle.

        The stored giveaway changes under its guild's lock, so joins at once all count. The post
        is updated through the press, in one response that no channel rate limit delays (v3 edited
        it through the REST API), and the user is told in the giveaway's language. A drawn or
        ended giveaway answers that it is closed; a press from a message other than the post is
        acknowledged without a change, as in v3; an unknown giveaway answers that it is not found.
        """
        user_id, now = interaction.user.id, int(self.clock())

        def toggle(current: Instance) -> tuple[str, Instance]:
            if not _from_post(interaction, current):
                return "elsewhere", current
            return join(current, user_id, now)

        found = await self._change(interaction, giveaway_id, toggle)
        if found is None:
            return
        outcome, instance = found
        texts = self._giveaway_texts(instance)
        match outcome:
            case "elsewhere":
                await interaction.response.defer()
            case "closed":
                await _tell(interaction, texts.get("error.closed"))
            case _:
                await self._refresh(interaction, instance)
                await interaction.followup.send(texts.get(f"reply.{outcome}"), ephemeral=True)

    async def _change[T](
        self,
        interaction: discord.Interaction,
        giveaway_id: str | None,
        transition: Callable[[Instance], tuple[T, Instance]],
    ) -> tuple[T, Instance] | None:
        """Change the guild's stored giveaway, or say that it is not found and return None.

        v3's English-only ``Guild not found.`` and ``Invalid giveaway id.`` fold into the not found
        text, in the user's language.
        """
        guild_id = interaction.guild_id
        found = (
            None
            if guild_id is None or giveaway_id is None
            else await self.giveaways.change(guild_id, giveaway_id, transition)
        )
        if found is None:
            await _tell(interaction, self._texts(interaction).get("error.not-found"))
        return found

    async def _refresh(self, interaction: discord.Interaction, instance: Instance) -> None:
        """Replace the pressed post with the giveaway as stored now, through the press."""
        message = self.render_post(instance)
        await interaction.response.edit_message(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )

    def _giveaway_texts(self, instance: Instance) -> Texts:
        """The texts in the giveaway's language, its creator's."""
        return Texts(self.lang, language(self.lang, instance.locale_tag))

    async def draw(
        self, interaction: discord.Interaction, giveaway_id: str | None, *, reroll: bool
    ) -> None:
        """Draw the giveaway's winners, or draw them again, as v3's draw and reroll.

        The draw is stored under the guild's lock before anything is sent, so two draws, or a draw
        and the automatic draw, never both draw. The post is updated through the press and v3's
        ``draw-result`` follows ephemerally, both in the giveaway's language; a refusal gets v3's
        text.
        """
        drawer = Drawer(interaction.user.id, admin=interaction.permissions.administrator)
        now = int(self.clock())

        def transition(current: Instance) -> tuple[str, Instance]:
            return draw(current, drawer, reroll=reroll, now=now, rng=self.random)

        found = await self._change(interaction, giveaway_id, transition)
        if found is None:
            return
        outcome, instance = found
        texts = self._giveaway_texts(instance)
        if outcome != "drawn":
            end = {"ga@end": str(instance.config.end_at)}
            await _tell(interaction, texts.get(REFUSALS[outcome], end))
            return
        await self._refresh(interaction, instance)
        message = render_message(
            self.templates.message("draw-result", texts.locale),
            global_values(interaction.client) | result(instance, texts, reroll=reroll),
            build_id=IDS.build,
        )
        await interaction.followup.send(
            content=message.content, embeds=message.embeds, ephemeral=True
        )

    async def press(self, interaction: discord.Interaction, sub_action: str) -> None:
        """Handle a press of the builder's button ``sub_action``.

        Without the user's draft, or from a builder message other than the one that shows it, the
        user gets v3's session-expired text; v3 found the draft by the user and the guild only, so
        an older builder drove the newest draft. Unknown sub-actions get no response, as in v3.
        """
        session = self._session(interaction)
        if session is None:
            await _tell(interaction, self._texts(interaction).get("error.expired"))
            return
        match sub_action:
            case "remove-prize":
                await self._remove_prize(interaction, session)
            case "toggle-duplicate-policy":
                await self._switch_policy(interaction, session)
            case "confirm-create":
                await self._confirm(interaction, session)
            case "cancel":
                await self._cancel(interaction)
            case _ if sub_action in MODALS:
                await self._open_modal(interaction, session, sub_action)
            case _:
                pass

    async def submit(self, interaction: discord.Interaction, sub_action: str) -> None:
        """Handle a submission of the builder's modal ``sub_action``.

        As a press, without the draft the user gets the session-expired text. An unknown
        sub-action gets no response; v3 re-rendered the preview.
        """
        session = self._session(interaction)
        if session is None:
            await _tell(interaction, self._texts(interaction).get("error.expired"))
        elif sub_action in MODALS:
            await self._apply(interaction, session, sub_action)

    async def _open_modal(
        self, interaction: discord.Interaction, session: Session, sub_action: str
    ) -> None:
        """Open v3's modal ``sub_action`` in the user's language, pre-filled with the draft.

        As v3's ``Placeholder.get(event)`` with the ``ga@*`` values put in: the press's values and
        the draft's, inserted as written (v3 expanded them, and a title of ``%ga@title%`` threw).
        An empty value leaves the input empty, as v3's.
        """
        locale = language(self.lang, interaction.locale.value)
        draft = session.draft
        end_time = format_end_time(draft.end_at, self.config.zone) if draft.end_at > 0 else ""
        next_prize = {"ga@index": str(len(draft.prizes) + 1)}
        values = placeholder_values(interaction) | {
            "ga@title": draft.title,
            "ga@description": draft.description,
            "ga@end-time": end_time,
            "ga@sponsor": draft.sponsor,
            "ga@thumbnail": draft.thumbnail_url,
            "ga@prize-name": Texts(self.lang, locale).get("new-prize", next_prize),
        }
        modal = render_modal(self.templates.modal(sub_action, locale), values, build_id=IDS.build)
        await interaction.response.send_modal(modal)

    async def _apply(
        self, interaction: discord.Interaction, session: Session, sub_action: str
    ) -> None:
        """Change the draft with the submitted modal ``sub_action`` and update the builder.

        An invalid value gets v3's error ephemerally and leaves the draft. A valid one replaces
        the builder message through the submission (a modal opened from a message may update it),
        where v3 deferred and edited it through the command's 15-minute hook.
        """
        now = int(self.clock())
        values = modal_values(interaction.data)
        changed = submit(session.draft, sub_action, values, now, self.config.zone)
        if isinstance(changed, str):
            await _tell(interaction, self._texts(interaction).get(changed))
            return
        await self._update(interaction, session, changed)

    async def _update(
        self, interaction: discord.Interaction, session: Session, draft: Draft
    ) -> None:
        """Keep the user's new draft and show it in the builder that the interaction came from."""
        # The session was found by the user and this interaction's guild.
        self.drafts[interaction.user.id, cast("int", interaction.guild_id)] = replace(
            session, draft=draft
        )
        message = self._builder(interaction, draft)
        await interaction.response.edit_message(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )

    async def _remove_prize(self, interaction: discord.Interaction, session: Session) -> None:
        """Remove the draft's last prize and update the builder, or say there is none."""
        changed = remove_last_prize(session.draft)
        if changed is None:
            await _tell(interaction, self._texts(interaction).get("error.no-prize"))
            return
        await self._update(interaction, session, changed)

    async def _switch_policy(self, interaction: discord.Interaction, session: Session) -> None:
        """Switch the draft's winner policy and update the builder."""
        await self._update(interaction, session, switch_policy(session.draft))

    async def _confirm(self, interaction: discord.Interaction, session: Session) -> None:
        """Check the draft and the user's Administrator permission, then post the giveaway.

        As v3: the draft's first problem, else a user without Administrator (even when the guild
        let others run the command), gets v3's text ephemerally, and the draft stays.
        """
        missing = problem(session.draft, int(self.clock()))
        if missing is None and not interaction.permissions.administrator:
            missing = "error.not-admin"
        if missing is not None:
            await _tell(interaction, self._texts(interaction).get(missing))
            return
        await self._post(interaction, session)

    async def _post(self, interaction: discord.Interaction, session: Session) -> None:
        """Post the confirmed draft as a giveaway, then turn the builder into a link to it.

        The draft is taken before the first await, so a second press meanwhile gets the
        session-expired text; v3 removed it after the post and posted twice. When the post cannot
        be made or stored, the draft comes back (unless the user started another one), the builder
        stays, and ``create-failed`` tells the user why; v3 replaced the builder and kept an
        orphaned draft, or said nothing for the errors that JDA threw before sending.
        """
        user_id, guild_id = interaction.user.id, cast("int", interaction.guild_id)
        del self.drafts[user_id, guild_id]
        await interaction.response.defer()  # v3's deferEdit: the builder stays for now
        try:
            posted = await self._create(interaction, guild_id, session.draft)
        except PostError as error:
            logger.warning(
                "Giveaway cannot post a giveaway in channel %s of guild %s: %s",
                interaction.channel_id,
                guild_id,
                error,
            )
            self.drafts.setdefault((user_id, guild_id), session)
            failed = self._render(interaction, "create-failed", {"ga@error": str(error)})
            await interaction.followup.send(
                content=failed.content, embeds=failed.embeds, ephemeral=True
            )
            return
        finished = self._render(interaction, "create-finished", {"ga@jump-url": posted.jump_url})
        await interaction.edit_original_response(
            content=finished.content,
            embeds=finished.embeds,
            view=finished.view,
            attachments=finished.files,
        )

    async def _create(
        self, interaction: discord.Interaction, guild_id: int, draft: Draft
    ) -> Posted:
        """Post ``draft`` in the interaction's channel and store it as a new giveaway.

        As v3: a new ID unused in the guild, the creator's locale, ``giveaway-post``, then the
        giveaway with the post's ID; a post whose giveaway cannot be stored is deleted.

        Raises:
            PostError: The channel takes no messages or refused the post, or the store failed.
        """
        channel, channel_id = _postable(interaction.channel), interaction.channel_id
        if channel is None or channel_id is None:
            msg = "the channel takes no messages"
            raise PostError(msg)
        try:
            taken = await self.giveaways.ids(guild_id)
        except DataError as error:
            raise PostError(str(error)) from error
        instance = Instance(
            id=new_id(taken, lambda: uuid.uuid4().hex),
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=0,
            creator_id=interaction.user.id,
            config=draft,
            locale_tag=interaction.locale.value,
            created_at=int(self.clock()),
        )
        message = self.render_post(instance)
        try:
            posted = await channel.send(
                content=message.content or None,
                embeds=message.embeds,
                view=message.view,
                files=message.files,
            )
        except discord.HTTPException as error:
            raise PostError(str(error)) from error
        try:
            await self.giveaways.add(replace(instance, message_id=posted.id))
        except (DataError, sqlite3.Error) as error:
            await _delete(posted)
            raise PostError(str(error)) from error
        return posted

    def _render(
        self, interaction: discord.Interaction, name: str, values: Mapping[str, str]
    ) -> Message:
        """Template ``name`` in the user's language with v3's global values and ``values``."""
        locale = language(self.lang, interaction.locale.value)
        return render_message(
            self.templates.message(name, locale),
            global_values(interaction.client) | dict(values),
            build_id=IDS.build,
        )

    async def _cancel(self, interaction: discord.Interaction) -> None:
        """Drop the user's draft and replace the builder with ``create-cancelled`` alone.

        As v3's replace edit, the preview and the buttons go; v3 edited through the command's
        hook, which expired after 15 minutes.
        """
        del self.drafts[interaction.user.id, cast("int", interaction.guild_id)]
        message = self._render(interaction, "create-cancelled", {})
        await interaction.response.edit_message(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )

    def _session(self, interaction: discord.Interaction) -> Session | None:
        """The user's draft in the guild, if the interaction comes from the builder showing it."""
        guild_id = interaction.guild_id
        session = None if guild_id is None else self.drafts.get((interaction.user.id, guild_id))
        message = interaction.message
        if session is None or message is None or message.id != session.message_id:
            return None
        return session

    def _texts(self, interaction: discord.Interaction) -> Texts:
        """The texts in the user's language."""
        return Texts(self.lang, language(self.lang, interaction.locale.value))

    def render_post(self, instance: Instance) -> Message:
        """The giveaway's post, v3's ``giveaway-post`` in the creator's language.

        As v3's, without a substitutor: v3's global values, and the embed and buttons as models.
        """
        locale = language(self.lang, instance.locale_tag)
        texts = Texts(self.lang, locale)
        now = int(self.clock())
        join, draw, reroll = post_buttons(instance, texts, now, IDS.build)
        models = {
            "ga@giveaway-embed": post_embed(instance, texts, now),
            "ga@join-button": join,
            "ga@draw-button": draw,
            "ga@reroll-button": reroll,
        }
        return render_message(
            self.templates.message("giveaway-post", locale),
            global_values(self.bot),
            build_id=IDS.build,
            models=models,
        )

    def _builder(self, interaction: discord.Interaction, draft: Draft) -> Message:
        """v3's ``create-giveaway`` with the preview of ``draft``, in the user's language.

        v3 rendered it without a substitutor: v3's global values.
        """
        locale = language(self.lang, interaction.locale.value)
        embed = preview(draft, Texts(self.lang, locale), self.config.zone)
        return render_message(
            self.templates.message("create-giveaway", locale),
            global_values(interaction.client),
            build_id=IDS.build,
            models={"ga@preview-embed": embed},
        )


async def _tell(interaction: discord.Interaction, text: str) -> None:
    """Answer the interaction with ``text``, ephemerally, as v3's replies."""
    await interaction.response.send_message(text, ephemeral=True)


def _postable(channel: object) -> Postable | None:
    """``channel`` if it takes messages, typed by the call that the plugin makes.

    discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union.
    """
    return channel if isinstance(channel, Postable) else None


async def _delete(posted: Posted) -> None:
    """Delete a post whose giveaway was not stored, as v3 did; a failure is logged."""
    try:
        await posted.delete()
    except discord.HTTPException as error:
        logger.warning(
            "Giveaway cannot delete the post %s, which it did not store: %s", posted.id, error
        )


def _from_post(interaction: discord.Interaction, instance: Instance) -> bool:
    """Whether the press comes from the giveaway's post, as v3 compared the message IDs."""
    message = interaction.message
    return message is not None and message.id == instance.message_id
