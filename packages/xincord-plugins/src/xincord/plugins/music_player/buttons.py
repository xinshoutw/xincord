"""The panels' five buttons, a base of the cog.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/Event.kt:96-118
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:298-333
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:783-956
"""

from typing import TYPE_CHECKING

from .replies import Replies

if TYPE_CHECKING:
    import discord

    from xincord.core.component_ids import ParsedId


class Buttons(Replies):
    """The buttons' handlers, a base of the cog, which sets the attributes."""

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """A press of a panel's button; ``setup`` routes v3's IDs and the new ones here."""
        raise NotImplementedError
