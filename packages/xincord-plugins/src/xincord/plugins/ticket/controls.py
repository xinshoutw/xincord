"""A ticket channel's control row (lock, unlock, delete and save), and the texts of every reply.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:148-242
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:312-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:834-852
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import discord

from .ids import IDS
from .model import Controls
from .texts import Texts, readable_error, tell
from .tickets import is_staff, viewing
from .views import control_row

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from discord.abc import Snowflake

    from xincord.core.i18n import Lang

    from .model import Entry
    from .store import Panels

logger = logging.getLogger(__name__)

SNOWFLAKE = re.compile(r"[1-9][0-9]{0,19}")  # a user ID in decimal, as the parsed IDs give it


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


class ChannelError(Exception):
    """The control row's channel cannot take the change; the message says why, for the user."""


class ControlRow:
    """The handlers of a ticket channel's control row, a base of the cog, which sets the
    attributes; the cog's own handlers use its texts too."""

    lang: Lang
    panels: Panels

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

        Acknowledged at once: v3 answered after fetching the member and setting the overwrite,
        within Discord's three seconds or not at all. The overwrite's other permissions stay. No
        permission check, as in v3: anyone who sees the channel may press it, the member too. A
        failure (the member left, a refused overwrite) is told to the user, and the row stays as
        it was. A row whose member is no user ID gets no response: v3 threw.
        """
        controls = _controls(fields)
        if controls is None:
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
        """Delete the ticket channel for its staff; anyone else gets an acknowledgement only.

        The entry of the row's panel button names the staff roles (v3's not-found text without
        one). As in v3, every press is acknowledged first, and nothing else happens for those who
        are no staff or no members; a refused deletion is told to the user.
        """
        found = await self._staff_entry(interaction, fields)
        if found == "error.not-found":
            await tell(interaction, self.texts(interaction).get("error.not-found"))
            return
        await interaction.response.defer()  # v3's deferEdit
        if isinstance(found, str):  # no member, or no staff
            return
        try:
            await _remove(interaction)
        except (discord.HTTPException, ChannelError) as error:
            logger.warning(
                "Ticket cannot delete the ticket channel %s: %s", interaction.channel_id, error
            )
            await self._failed(interaction, "error.delete-failed", error)

    async def save(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Offer the ticket's staff a select of the text channel to save the conversation in."""
        raise NotImplementedError

    async def select_target(
        self, interaction: discord.Interaction, fields: Mapping[str, str], values: Sequence[str]
    ) -> None:
        """Check the chosen channel and the bot's permissions, then save the conversation there."""
        raise NotImplementedError

    async def _staff_entry(
        self, interaction: discord.Interaction, fields: Mapping[str, str]
    ) -> Entry | str:
        """The entry of the row's panel button when one of its staff acted, else the error key
        that refuses: ``error.no-member``, ``error.not-found`` or ``error.admin-only``, in v3's
        order.

        Staff hold one of the entry's roles, or Administrator (v3's ``hasTicketAdminPermission``).
        """
        roles = _role_ids(interaction.user)
        if roles is None:
            return "error.no-member"
        guild_id = cast("int", interaction.guild_id)  # members act in guilds
        message_id, index = fields.get("msg_id", ""), fields.get("btn_index", "")
        entry = await self.panels.entry(guild_id, message_id, index)
        if entry is None:
            return "error.not-found"
        if not is_staff(roles, entry, administrator=interaction.permissions.administrator):
            return "error.admin-only"
        return entry

    async def _failed(self, interaction: discord.Interaction, key: str, error: Exception) -> None:
        """Tell the user, after the acknowledgement, the text ``key`` with ``error``."""
        failed = self.texts(interaction).get(key, {"tt@error": readable_error(error)})
        await interaction.followup.send(failed, ephemeral=True)


def _role_ids(user: object) -> frozenset[int] | None:
    """The IDs of a member's roles; None for a user who is no member (v3's ``event.member``)."""
    return frozenset(role.id for role in user.roles) if isinstance(user, HasRoles) else None


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
