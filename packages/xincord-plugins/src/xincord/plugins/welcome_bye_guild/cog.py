"""The channel commands and the join and removal listeners.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:30-303
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/command/Register.kt:12-75
"""

from typing import TYPE_CHECKING, NamedTuple

from discord.ext import commands

from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

from .store import read, set_channel
from .values import command_values, text_channel

if TYPE_CHECKING:
    import discord
    from discord import app_commands

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .store import Kind


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
