"""The channel commands and the join and removal listeners.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:30-303
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/command/Register.kt:12-75
"""

import logging
from typing import TYPE_CHECKING, NamedTuple, Protocol, override, runtime_checkable

import discord
from discord.ext import commands

from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

from .store import forget, guild_ids, read, set_channel
from .values import TextChannelLike, command_values, member_event_values, text_channel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .store import Kind


logger = logging.getLogger(__name__)


@runtime_checkable
class Postable(TextChannelLike, Protocol):
    """A text channel that takes messages, as the plugin calls it."""

    async def send(
        self,
        *,
        content: str | None = None,
        embeds: Sequence[discord.Embed] = (),
        view: discord.ui.View | discord.ui.LayoutView | None = None,
        files: Sequence[discord.File] = (),
    ) -> object:
        """Send a message to the channel."""
        ...


class CommandSpec(NamedTuple):
    """One of v3's commands: the kind of channel it changes and v3's default texts."""

    kind: Kind
    description: str
    option: str | None = None  # the channel option's description, for the bind commands


# v3's commands, in v3's order.
COMMANDS = {
    "welcome-channel-bind": CommandSpec(
        "welcome", "bind channel for welcome message", "welcome output channel"
    ),
    "welcome-channel-unbind": CommandSpec("welcome", "unbind welcome channel"),
    "bye-channel-bind": CommandSpec("bye", "bind channel for bye message", "bye output channel"),
    "bye-channel-unbind": CommandSpec("bye", "unbind bye channel"),
}


class WelcomeByeGuild(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates

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
        """Delete the channels of a guild that the bot left or was removed from, as v3 did.

        discord.py does not fire this during an outage (``on_guild_unavailable``).
        """
        await forget(self.store, guild.id)

    async def forget_left_guilds(self) -> None:
        """Delete the channels of the guilds the bot is no longer in.

        v3 deleted them only when it saw the bot leave a guild while the plugin was enabled. By
        ``on_ready``, discord.py knows every guild of the session, unavailable ones included.
        """
        for guild_id in await guild_ids(self.store):
            if self.bot.get_guild(guild_id) is None:
                await forget(self.store, guild_id)
                logger.info(
                    "WelcomeByeGuild deleted the channels of guild %s, which the bot left",
                    guild_id,
                )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Welcome a member, bots too as in v3, in the guild's welcome channel.

        discord.py builds the member from the event and counts it in the guild beforehand, as JDA
        did, so ``%wbg@guild_member_count%`` includes it.
        """
        await self._greet(member.guild, member, "welcome", "join")

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        """See off a member who left, was kicked or banned, in the guild's bye channel.

        ``on_member_remove`` fires only for cached members; the raw event has the member when
        discord.py had it, else the user. JDA ignored the bot's own removal, and so does this.
        """
        bot = self.bot.user
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None or (bot is not None and payload.user.id == bot.id):
            return
        await self._greet(guild, payload.user, "bye", "leave")

    async def _greet(
        self,
        guild: discord.Guild,
        user: discord.User | discord.Member,
        kind: Kind,
        event_type: str,
    ) -> None:
        """Send the ``kind`` message to the guild's ``kind`` channel, in the guild's locale.

        As in v3, nothing is sent when the channel is unbound, gone or not a text channel. When
        Discord refuses the message, a warning names the guild and the channel.
        """
        bindings = await read(self.store, guild.id)
        channel_id = bindings.channel(kind)
        channel = _postable(guild.get_channel(channel_id)) if channel_id else None
        if channel is None:
            return
        values = member_event_values(self.bot.user, user, guild, bindings, event_type)
        template = self.templates.message(kind, guild.preferred_locale.value)
        message = render_message(template, values)
        try:
            await channel.send(
                content=message.content or None,
                embeds=message.embeds,
                view=message.view,
                files=message.files,
            )
        except discord.HTTPException as error:
            logger.warning(
                "WelcomeByeGuild cannot post the %s message in %s (%s) of %s (%s): %s",
                kind,
                channel.name,
                channel.id,
                guild.name,
                guild.id,
                error,
            )

    async def bind_channel(
        self,
        interaction: discord.Interaction,
        channel: app_commands.AppCommandChannel | None = None,
    ) -> None:
        """Bind the option's text channel, else the command's, as the welcome or bye channel.

        The option offers text channels only; without it, the command's channel must be one, so a
        thread, a voice channel's chat or an announcement channel gets ``invalid-channel``.
        """
        guild = await self._guild(interaction)
        if guild is None:
            return
        kind = _kind(interaction)
        target = text_channel(interaction.channel if channel is None else channel)
        if target is None:
            values = command_values(interaction, guild, await read(self.store, guild.id))
            await self._reply(interaction, "invalid-channel", values)
            return
        bindings, previous = await set_channel(self.store, guild.id, kind, target.id)
        state = "already" if previous == target.id else "success"
        values = command_values(interaction, guild, bindings, selected=target)
        await self._reply(interaction, f"{kind}-bind-{state}", values)

    async def unbind_channel(self, interaction: discord.Interaction) -> None:
        """Unbind the guild's welcome or bye channel; the reply mentions the previous one."""
        guild = await self._guild(interaction)
        if guild is None:
            return
        kind = _kind(interaction)
        bindings, previous = await set_channel(self.store, guild.id, kind, 0)
        state = "success" if previous else "empty"
        values = command_values(interaction, guild, bindings, previous=previous)
        await self._reply(interaction, f"{kind}-unbind-{state}", values)

    async def _guild(self, interaction: discord.Interaction) -> discord.Guild | None:
        """The command's guild if the user may change its channels; else reply why not.

        The commands are hidden from members without Administrator, but a guild can grant them in
        its integration settings, so v3 also checked the permission when they ran. The owner and
        administrators have every permission in the channel, and Administrator cannot be set per
        channel, so the interaction's permissions answer as JDA's ``hasPermission`` did.
        """
        guild = interaction.guild
        if guild is None:  # discord.py gives commands in a guild one, even when not cached
            await self._reply(interaction, "guild-only", placeholder_values(interaction))
        elif not interaction.permissions.administrator:
            await self._reply(interaction, "no-permission", placeholder_values(interaction))
        else:
            return guild
        return None

    async def _reply(
        self, interaction: discord.Interaction, key: str, values: dict[str, str]
    ) -> None:
        """Edit the deferred ephemeral response into the message ``key``.

        As in v3, it is rendered in the guild's preferred locale, or the user's outside a guild.
        """
        locale = (interaction.guild_locale or interaction.locale).value
        reply = render_message(self.templates.message(key, locale), values)
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=reply.content, embeds=reply.embeds, view=reply.view, attachments=reply.files
        )


def _kind(interaction: discord.Interaction) -> Kind:
    """The kind of channel that the invoked command changes."""
    name = interaction.command.name if interaction.command else ""
    return COMMANDS[name].kind


def _postable(channel: object) -> Postable | None:
    """``channel`` if it is a text channel, typed by the call that the plugin makes.

    discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union.
    """
    text = text_channel(channel)
    return text if isinstance(text, Postable) else None
