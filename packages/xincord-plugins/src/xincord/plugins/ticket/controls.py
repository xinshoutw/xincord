"""A ticket channel's control row (lock, unlock, delete and save), and the texts of every reply.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:148-242
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:312-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:834-852
"""

from typing import TYPE_CHECKING

from .texts import Texts

if TYPE_CHECKING:
    from collections.abc import Mapping

    import discord

    from xincord.core.i18n import Lang

    from .store import Panels


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
        """Deny or allow the ticket's member View Channel, then show the other control row."""
        raise NotImplementedError
