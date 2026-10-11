"""Rendering and answering: the panels' screens and the texts, a base of the cog."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import discord

from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message
from xincord.plugins.redaction import redact

from .display import QUEUE_COLOR, Look, emoji_values, queue_embed, track_values
from .history import Requester
from .ids import IDS
from .session import Session
from .texts import describe, raw, text

if TYPE_CHECKING:
    from collections.abc import Mapping

    from discord.ext import commands

    from xincord.core.i18n import Lang
    from xincord.core.templates import Message, Templates

    from .audio import Link
    from .config import Config
    from .history import Entry
    from .panels import Panels

# v3's model key of the queue panel's list, which v3 (and the core) looked up as written.
QUEUE_MODEL = "%music_player@player_track_list_model_key%"


@dataclass(frozen=True)
class Screen:
    """What a panel shows: its template, and the levels of a volume panel."""

    template: str
    levels: tuple[int, int] | None = None  # the volume before and after


class Replies:
    """The rendering and the answers that the commands and the buttons share, a base of the cog,
    which sets the attributes."""

    bot: commands.Bot
    config: Config
    lang: Lang
    templates: Templates
    sessions: dict[int, Session]
    emojis: Mapping[str, str]
    link: Link | None
    panels: Panels

    def changed(self, session: Session) -> None:
        """A session started or stopped playing, or connected or disconnected."""

    def session(self, guild_id: int) -> Session:
        """The guild's session, created at the config's default volume when it has none."""
        if (found := self.sessions.get(guild_id)) is None:
            volume = self.config.player.default_volume
            found = self.sessions[guild_id] = Session(guild_id, volume, self.changed)
        return found

    def text(self, key: str, locale: str, **values: object) -> str:
        """The text ``key`` of ``text.yaml`` in ``locale``, else zh-TW, with ``values``."""
        return text(self.lang, key, locale, **values)

    def look(self, locale: str) -> Look:
        """The emojis and the locale's words that a panel shows."""
        return Look(
            self.emojis,
            live=self.text("live", locale),
            live_length=self.text("live-length", locale),
        )

    def render(
        self,
        screen: Screen,
        session: Session,
        interaction: discord.Interaction,
        *,
        entry: Entry | None = None,
    ) -> Message:
        """Render ``screen`` for the user of ``interaction``, in their locale.

        A track panel shows ``entry`` from its start (a song just started or added), else the
        session's current song where it plays; the queue panel adds the upcoming songs; the volume
        panel shows its two levels.
        """
        locale = interaction.locale.value
        values = placeholder_values(interaction) | emoji_values(self.emojis)
        models: dict[str, object] | None = None
        if screen.levels is not None:
            before, after = screen.levels
            values |= {
                "music_player@player_volume_before": str(before),
                "music_player@player_volume_after": str(after),
            }
        else:
            values |= track_values(
                entry if entry is not None else session.current(),
                position=0 if entry is not None else session.position(),
                playing=session.playing and not session.paused,
                loop=session.loop,
                look=self.look(locale),
            )
            if screen.template == "queue":
                models = {QUEUE_MODEL: self.queue_view(session, locale)}
        template = self.templates.message(screen.template, locale)
        return render_message(template, values, build_id=IDS.build, models=models)

    def queue_view(self, session: Session, locale: str) -> discord.Embed:
        """The queue panel's list of the upcoming songs, or ``empty-playlist`` when none."""
        upcoming = session.history.upcoming
        if not upcoming:
            return discord.Embed(
                colour=QUEUE_COLOR, description=self.text("empty-playlist", locale)
            )
        live_length = self.text("live-length", locale)
        return queue_embed(
            upcoming, live_length=live_length, more=raw(self.lang, "queue-more", locale)
        )

    async def tell(self, interaction: discord.Interaction, key: str, **values: object) -> None:
        """Edit the response's content into the text ``key``, as v3's ``editOriginal(text)``."""
        content = self.text(key, interaction.locale.value, **values)
        await interaction.edit_original_response(content=content)

    async def report(
        self, interaction: discord.Interaction, key: str, error: BaseException
    ) -> None:
        """Tell the user about an unexpected error: ``key`` with its text, URLs cut to their
        origin, or ``<key>-hidden`` without ``messages.show_detailed_errors``, as v3."""
        if self.config.messages.show_detailed_errors:
            await self.tell(interaction, key, error=redact(describe(error)))
        else:
            await self.tell(interaction, f"{key}-hidden")

    async def show(
        self,
        interaction: discord.Interaction,
        screen: Screen,
        session: Session,
        *,
        entry: Entry | None = None,
        content: str = "",
    ) -> None:
        """Edit the command's response into the panel ``screen``, ``content`` above it, and track
        the panel, which then refreshes itself (v3 tracked it after a successful edit)."""
        message = self.render(screen, session, interaction, entry=entry)
        sent = await interaction.edit_original_response(
            content=content or message.content, embeds=list(message.embeds), view=message.view
        )
        guild = session.guild_id
        await self.panels.open(interaction.user.id, guild, sent.id, screen, interaction)

    async def redraw(
        self, interaction: discord.Interaction, session: Session, entry: Entry | None = None
    ) -> None:
        """Edit a pressed panel into the ``now-playing`` screen, as v3's buttons did; any text
        above it goes."""
        message = self.render(Screen("now-playing"), session, interaction, entry=entry)
        await interaction.edit_original_response(
            content=message.content, embeds=list(message.embeds), view=message.view
        )


def requester(member: discord.Member | discord.User) -> Requester:
    """The member who adds a song, as v3 kept them: ID, display name, username and avatar."""
    return Requester(member.id, member.display_name, member.name, member.display_avatar.url)


def guild_of(interaction: discord.Interaction) -> discord.Guild:
    """The interaction's guild: the plugin's commands and panels are in guilds only."""
    return cast("discord.Guild", interaction.guild)


def voice_channel(interaction: discord.Interaction) -> discord.VoiceChannel | None:
    """The member's voice channel, a stage included; None outside voice."""
    voice = cast("discord.VoiceState | None", getattr(interaction.user, "voice", None))
    return None if voice is None else cast("discord.VoiceChannel | None", voice.channel)
