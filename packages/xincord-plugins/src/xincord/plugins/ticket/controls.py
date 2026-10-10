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
from .texts import Texts, readable_error
from .tickets import viewing
from .views import control_row

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.i18n import Lang

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
            failed = self.texts(interaction).get(
                "error.lock-failed", {"tt@error": readable_error(error)}
            )
            await interaction.followup.send(failed, ephemeral=True)
            return
        row = control_row(controls, locked=locked, texts=self.public, build_id=IDS.build)
        await interaction.edit_original_response(view=row)

    async def delete(self, interaction: discord.Interaction, fields: Mapping[str, str]) -> None:
        """Delete the ticket channel for its staff; anyone else gets an acknowledgement only."""
        raise NotImplementedError


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
