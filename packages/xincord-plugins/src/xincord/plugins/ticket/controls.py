"""A ticket channel's control row (lock, unlock, delete and save), and the texts of every reply.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:148-242
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:312-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:834-852
"""

import logging
import re
import traceback
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import discord

from xincord.plugins.redaction import redact

from .archive import Options, archive
from .channels import cached_channel
from .ids import IDS
from .model import Controls
from .texts import Texts, readable_error, tell
from .tickets import is_staff, viewing
from .views import control_row, save_select

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import tzinfo

    from discord.abc import Snowflake

    from xincord.core.i18n import Lang

    from .channels import ArchiveTarget, History
    from .model import Entry
    from .store import Panels

logger = logging.getLogger(__name__)

SNOWFLAKE = re.compile(r"[1-9][0-9]{0,19}")  # a user ID in decimal, as the parsed IDs give it
# What the bot needs in the ticket channel, and in the chosen channel, to save the conversation.
READ = discord.Permissions(view_channel=True, read_message_history=True)
POST = discord.Permissions(
    view_channel=True,
    send_messages=True,
    send_messages_in_threads=True,
    create_public_threads=True,
    manage_webhooks=True,
)


@runtime_checkable
class Members(Protocol):
    """A guild whose members are found in discord.py's cache, else asked of Discord."""

    def get_member(self, user_id: int, /) -> object:
        """The cached member ``user_id``, or None."""
        ...

    async def fetch_member(self, member_id: int, /) -> object:
        """The member ``member_id``, as Discord has them."""
        ...


@runtime_checkable
class Overwritten(Protocol):
    """A guild channel whose permission overwrites the control row changes."""

    def overwrites_for(self, obj: Any, /) -> discord.PermissionOverwrite:  # noqa: ANN401 - discord.py's
        """The overwrite of ``obj`` in the channel, a copy."""
        ...

    async def set_permissions(
        self,
        target: Any,  # noqa: ANN401 - discord.py's
        /,
        *,
        overwrite: discord.PermissionOverwrite | None,
    ) -> None:
        """Replace the overwrite of ``target``."""
        ...


@runtime_checkable
class Removable(Protocol):
    """A channel that can be deleted."""

    async def delete(self) -> None:
        """Delete the channel."""
        ...


@runtime_checkable
class HasRoles(Protocol):
    """A guild member, whose roles may make them a ticket's staff."""

    @property
    def roles(self) -> Sequence[Snowflake]:
        """The member's roles."""
        ...


@runtime_checkable
class CheckedChannel(Protocol):
    """A guild channel that a save checks: its type and the bot's permissions in it."""

    @property
    def id(self) -> int:
        """The channel's ID."""
        ...

    @property
    def type(self) -> discord.ChannelType:
        """The channel's type."""
        ...

    def permissions_for(self, obj: Any, /) -> discord.Permissions:  # noqa: ANN401 - discord.py's
        """The permissions of ``obj`` in the channel."""
        ...


class ChannelError(Exception):
    """The control row's channel cannot take the change; the message says why, for the user."""


class ControlRow:
    """The handlers of a ticket channel's control row, a base of the cog, which sets the
    attributes; the cog's own handlers use its texts too."""

    lang: Lang
    panels: Panels
    clock: Callable[[], float]  # the archive's time, in seconds since the epoch
    zone: tzinfo | None  # the time zone of the archive's names and markers; None: the host's

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

    async def lock(
        self, interaction: discord.Interaction, fields: Mapping[str, str], *, locked: bool
    ) -> None:
        """Deny (``locked``) or allow the ticket's member View Channel, then show the other row.

        For the ticket's staff only (:meth:`_staff`): anyone else, the ticket's member too, is
        refused and nothing changes; v3 checked nobody, so the member could lock themselves out.
        Only the store is read before the acknowledgement, which comes before any request to
        Discord: v3 answered after fetching the member and setting the overwrite, within
        Discord's three seconds or not at all. The overwrite's other permissions stay. A failure
        (the member left, a refused overwrite) is told to the user, and the row stays as it was.
        A row whose member is no user ID gets no response from anyone: v3 threw.
        """
        controls = _controls(fields)
        if controls is None:
            return
        if await self._staff(interaction, fields) is None:
            return
        await interaction.response.defer()
        try:
            await _permit(interaction, controls.user_id, allowed=not locked)
        except (discord.HTTPException, ChannelError) as error:
            logger.warning(
                "Ticket cannot %s channel %s for member %s: %s",
                "lock" if locked else "unlock",
                interaction.channel_id,
                controls.user_id,
                error,
            )
            await self._failed(interaction, "error.lock-failed", error)
            return
        row = control_row(controls, locked=locked, texts=self.public, build_id=IDS.build)
        await interaction.edit_original_response(view=row)

    async def delete(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Delete the ticket channel for its staff (:meth:`_staff`); anyone else is refused.

        v3 acknowledged anyone but staff and did nothing. The staff's press is acknowledged before
        the deletion (v3's ``deferEdit``), and a refused deletion is told to the user.
        """
        if await self._staff(interaction, fields) is None:
            return
        await interaction.response.defer()  # v3's deferEdit
        try:
            await _remove(interaction)
        except (discord.HTTPException, ChannelError) as error:
            logger.warning(
                "Ticket cannot delete the ticket channel %s: %s", interaction.channel_id, error
            )
            await self._failed(interaction, "error.delete-failed", error)

    async def save(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Offer the ticket's staff (:meth:`_staff`), ephemerally, a select of the text channel to
        save it in; anyone else is refused, as in v3.

        The select's ID carries the row's fields; a row whose member is no user ID gets no
        response (v3 threw).
        """
        if await self._staff(interaction, fields) is None:
            return
        controls = _controls(fields)
        if controls is None:
            return
        texts = self.texts(interaction)
        await interaction.response.send_message(
            texts.get("reply.choose-channel"),
            view=save_select(controls, texts, IDS.build),
            ephemeral=True,
        )

    async def select_target(
        self, interaction: discord.Interaction, fields: Mapping[str, str], values: Sequence[str]
    ) -> None:
        """Check a save select's choice, then save the conversation into the chosen channel.

        Another select gets v3's acknowledgement only. The checks run in v3's order, each refusal
        answering its text: a member, the entry, staff, the ticket a text channel, a text channel
        chosen, the bot's View Channel and Read Message History in the ticket, and its View
        Channel, Send Messages, Send Messages in Threads, Create Public Threads and Manage
        Webhooks in the chosen channel.
        """
        if fields.get("sub_action") != "select-channel":
            await interaction.response.defer()  # v3's deferEdit
            return
        found = await self._staff_entry(interaction, fields)
        checked = found if isinstance(found, str) else _save_channels(interaction, values)
        if isinstance(checked, str):
            await tell(interaction, self.texts(interaction).get(checked))
            return
        await self._save(interaction, *checked)

    async def _save(
        self, interaction: discord.Interaction, source: CheckedChannel, target: CheckedChannel
    ) -> None:
        """Archive ``source`` into a new thread of ``target`` and tell the user how it went.

        A new ephemeral answer, v3's ``deferReply``, so that the select stays usable; it says that
        the archive is under way, then where it went, or v3's save-failed text with the error. The
        markers use the default locale, as v3's. An answer that Discord refuses, after its 15
        minutes, is logged.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        texts = self.texts(interaction)
        await interaction.edit_original_response(content=texts.get("reply.saving"))
        guild = cast("discord.Guild", interaction.guild)  # members act in guilds
        options = Options(self.public, self.clock(), self.zone, guild.filesize_limit)
        try:
            thread = await archive(cast("History", source), cast("ArchiveTarget", target), options)
        except Exception as error:  # noqa: BLE001 - every failure is told, as v3's onError
            logger.warning(
                "Ticket cannot save channel %s into channel %s: %s",
                source.id,
                target.id,
                _logged(error),
            )
            answer = texts.get("error.save-failed", {"tt@error": readable_error(error)})
        else:
            answer = texts.get("reply.saved", {"tt@thread": thread.mention})
        try:
            await interaction.edit_original_response(content=answer)
        except discord.HTTPException as error:
            logger.warning(
                "Ticket cannot tell member %s how saving channel %s went: %s",
                interaction.user.id,
                source.id,
                error,
            )

    async def _staff_entry(
        self, interaction: discord.Interaction, fields: Mapping[str, str]
    ) -> Entry | str:
        """The entry of the row's panel button when one of its staff acted, else the error key
        that refuses: ``error.no-member``, ``error.not-found`` or ``error.admin-only``, in v3's
        order.

        Staff hold one of the entry's roles, or Administrator (v3's ``hasTicketAdminPermission``).
        """
        guild_id = cast("int", interaction.guild_id)  # members act in guilds
        roles = _role_ids(interaction.user, guild_id)
        if roles is None:
            return "error.no-member"
        message_id, index = fields.get("msg_id", ""), fields.get("btn_index", "")
        entry = await self.panels.entry(guild_id, message_id, index)
        if entry is None:
            return "error.not-found"
        if not is_staff(roles, entry, administrator=interaction.permissions.administrator):
            return "error.admin-only"
        return entry

    async def _staff(
        self, interaction: discord.Interaction, fields: Mapping[str, str]
    ) -> Entry | None:
        """The entry of the row's panel button when one of its staff pressed a button of the
        control row; otherwise the press is refused (:meth:`_refuse`) and None returned.

        The one check of lock, unlock, save and delete, at the owner's request: v3 checked save
        and delete only, and acknowledged anyone but staff on delete without a word.
        """
        found = await self._staff_entry(interaction, fields)
        if isinstance(found, str):
            await self._refuse(interaction, found)
            return None
        return found

    async def _refuse(self, interaction: discord.Interaction, key: str) -> None:
        """Answer a press of the control row that the ticket's staff did not make; ``key`` is
        what :meth:`_staff_entry` refused it with.

        A user who is no member gets v3's acknowledgement only (Discord sends the member with
        every interaction in a guild, so this happens outside guilds only); anyone else the text
        ``key``, not-found or admin-only, as the interaction's ephemeral response.
        """
        if key == "error.no-member":
            await interaction.response.defer()  # v3's deferEdit
            return
        await tell(interaction, self.texts(interaction).get(key))

    async def _failed(self, interaction: discord.Interaction, key: str, error: Exception) -> None:
        """Tell the user, after the acknowledgement, the text ``key`` with ``error``."""
        failed = self.texts(interaction).get(key, {"tt@error": readable_error(error)})
        await interaction.followup.send(failed, ephemeral=True)


def _role_ids(user: object, guild_id: int) -> frozenset[int] | None:
    """The IDs of a member's roles but @everyone's, which is the guild's ID; None for a user who
    is no member (v3's ``event.member``).

    discord.py lists @everyone among every member's roles, where JDA's ``getRoles`` left it out:
    an entry naming it would make every member staff.
    """
    if not isinstance(user, HasRoles):
        return None
    return frozenset(role.id for role in user.roles) - {guild_id}


def _controls(fields: Mapping[str, str]) -> Controls | None:
    """What a control row's ID carries; None when its member is no user ID."""
    user_id = fields.get("user_id", "")
    if not SNOWFLAKE.fullmatch(user_id):
        return None
    return Controls(int(user_id), fields.get("msg_id", ""), fields.get("btn_index", ""))


async def _permit(interaction: discord.Interaction, user_id: int, *, allowed: bool) -> None:
    """Allow or deny the member ``user_id`` View Channel in the interaction's channel, the
    overwrite's other permissions kept (JDA's ``upsertPermissionOverride``).

    The member comes from discord.py's cache, else from Discord (JDA's ``retrieveMemberById``).

    Raises:
        discord.HTTPException: The member is not in the guild (NotFound), or Discord refused the
            overwrite.
        ChannelError: The channel has no permission overwrites.
    """
    channel = cast("object", interaction.channel)
    guild = cast("object", interaction.guild)
    if not isinstance(channel, Overwritten) or not isinstance(guild, Members):
        msg = "this channel has no permission overwrites"
        raise ChannelError(msg)
    member = guild.get_member(user_id)
    if member is None:
        member = await guild.fetch_member(user_id)
    await channel.set_permissions(
        member, overwrite=viewing(channel.overwrites_for(member), allowed=allowed)
    )


def _save_channels(
    interaction: discord.Interaction, values: Sequence[str]
) -> tuple[CheckedChannel, CheckedChannel] | str:
    """The ticket channel and the chosen channel of a save, else the error key that refuses it.

    In v3's order: the ticket a text channel, a text channel among the choice, the bot's View
    Channel and Read Message History in the ticket, and what it needs to post in the other.
    """
    source = _text_channel(interaction.channel)
    if source is None:
        return "error.not-text-channel"
    guild = cast("discord.Guild", interaction.guild)  # members act in guilds
    target = _chosen(guild, values)
    if target is None:
        return "error.choose-text-channel"
    if not source.permissions_for(guild.me).is_superset(READ):
        return "error.no-history-permission"
    if not target.permissions_for(guild.me).is_superset(POST):
        return "error.no-target-permission"
    return source, target


def _chosen(guild: object, values: Sequence[str]) -> CheckedChannel | None:
    """The first of a select's values that the guild's cache knows as a text channel."""
    for value in values:
        channel = _text_channel(cached_channel(guild, value))
        if channel is not None:
            return channel
    return None


def _text_channel(channel: object) -> CheckedChannel | None:
    """``channel`` when it is a text channel (no thread, voice channel or forum), else None."""
    if isinstance(channel, CheckedChannel) and channel.type is discord.ChannelType.text:
        return channel
    return None


def _logged(error: Exception) -> str:
    """A failed archive's error as logged: Discord's refusal as it reads, anything else with its
    traceback; URLs cut to their origin, since a webhook's holds its token."""
    if isinstance(error, discord.HTTPException):
        return readable_error(error)
    return redact("".join(traceback.format_exception(error)).rstrip("\n"))


async def _remove(interaction: discord.Interaction) -> None:
    """Delete the interaction's channel.

    Raises:
        discord.HTTPException: Discord refused.
        ChannelError: The channel cannot be deleted.
    """
    channel = cast("object", interaction.channel)
    if not isinstance(channel, Removable):
        msg = "this channel cannot be deleted"
        raise ChannelError(msg)
    await channel.delete()
