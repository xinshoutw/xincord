"""The panels' five buttons, a base of the cog."""

import logging
from typing import TYPE_CHECKING, cast

import discord

from xincord.plugins.redaction import redact

from .audio import NodeUnavailableError
from .replies import Replies, guild_of, voice_channel
from .texts import format_traceback

if TYPE_CHECKING:
    from xincord.core.component_ids import ParsedId

    from .session import Session

logger = logging.getLogger(__name__)

ACTIONS = frozenset({"previous", "pause-resume", "skip", "loop", "disconnect"})  # v3's buttons


class Buttons(Replies):
    """The buttons' handlers, a base of the cog, which sets the attributes."""

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """A press of a panel's button; ``setup`` routes v3's IDs and the new ones here.

        Every press is acknowledged at once with a deferred update, then the panel shows the
        answer (v3 edited the panel without acknowledging its refusals, so members saw "This
        interaction failed", bug B3). The press keeps a tracked panel alive and edits it from then
        on. Other actions get no response, as in v3.
        """
        action = parsed.fields.get("action", "")
        if interaction.type is not discord.InteractionType.component or action not in ACTIONS:
            return
        await interaction.response.defer()
        self.panels.touch(_panel(interaction), interaction)
        try:
            await self.press(interaction, action)
        except NodeUnavailableError:
            await self.tell(interaction, "node-unavailable")
        except Exception as error:  # noqa: BLE001 - logged as redacted text, then answered
            logger.error(  # noqa: TRY400 - the traceback is in the text
                "MusicPlayer: the %s button failed:\n%s", action, redact(format_traceback(error))
            )
            await self.report(interaction, "button-error", error)

    async def press(self, interaction: discord.Interaction, action: str) -> None:
        """Act on the guild's player as v3's buttons did, for a member in voice (any channel)."""
        if voice_channel(interaction) is None:
            await self.tell(interaction, "button-join-voice")
            return
        guild = guild_of(interaction)
        session = self.sessions.get(guild.id)
        match action:
            case "disconnect":
                await self.disconnect(interaction, guild)
            case "loop":
                await self.loop(interaction, self.session(guild.id))
            case "previous":
                await self.previous(interaction, session)
            case _ if session is None or not session.playing:
                await self.tell(interaction, "nothing-playing")
            case "skip":
                if (entry := await session.skip()) is None:
                    await self.tell(interaction, "no-more-songs")
                else:
                    await self.redraw(interaction, session, entry)
            case _:  # pause-resume
                await session.toggle_pause()
                if session.playing:
                    await self.redraw(interaction, session)
                else:  # the songs went while the press waited for the player
                    await self.tell(interaction, "nothing-playing")

    async def previous(self, interaction: discord.Interaction, session: Session | None) -> None:
        """v3's previous button: restart the song after 5 seconds, else play the previous one.

        The song starts unpaused (v3 kept the pause, bug B22) and the panel shows it from 00:00.
        """
        if session is not None and (entry := await session.previous()) is not None:
            await self.redraw(interaction, session, entry)
        elif session is None or not session.history.entries:
            await self.tell(interaction, "previous-no-song")
        else:
            await self.tell(interaction, "previous-idle")

    async def loop(self, interaction: discord.Interaction, session: Session) -> None:
        """Toggle the loop mode, also while nothing plays, as v3; show it when a song plays."""
        session.toggle_loop()
        if session.playing:
            await self.redraw(interaction, session)

    async def disconnect(self, interaction: discord.Interaction, guild: discord.Guild) -> None:
        """Leave voice, which forgets the songs, and delete the pressed panel."""
        voice = guild.voice_client
        if voice is None:
            await self.tell(interaction, "not-connected")
            return
        self.panels.forget(_panel(interaction))
        await interaction.delete_original_response()
        await voice.disconnect(force=True)


def _panel(interaction: discord.Interaction) -> int:
    """The pressed panel's message: a button's interaction always has one."""
    return cast("discord.Message", interaction.message).id
