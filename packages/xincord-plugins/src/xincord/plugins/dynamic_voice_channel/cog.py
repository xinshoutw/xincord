"""The lobby commands, the voice listener and the checks when the bot is ready.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/DynamicVoiceChannel.kt:19-135
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/command/Register.kt:13-89
"""

import logging
from typing import TYPE_CHECKING, Any, NamedTuple, override

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

from .store import Binding, bind, unbind

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

logger = logging.getLogger(__name__)


class VoiceChannelOption(app_commands.Transformer[discord.Client]):
    """v3's ``channel`` options: Discord offers voice channels only, which JDA's cast required.

    A ``discord.VoiceChannel`` annotation would need the channel in discord.py's cache; this passes
    on the channel that Discord resolved. WelcomeByeGuild and Feedbacker have the same transformer
    for text channels.
    """

    @property
    @override
    def type(self) -> discord.AppCommandOptionType:
        """A channel option."""
        return discord.AppCommandOptionType.channel

    @property
    @override
    def channel_types(self) -> list[discord.ChannelType]:
        """Voice channels only; v3 threw for the others, stage channels included."""
        return [discord.ChannelType.voice]

    @override
    async def transform(self, interaction: discord.Interaction, value: object, /) -> object:
        """Pass on the ``AppCommandChannel`` that Discord resolved."""
        return value


class SubcommandSpec(NamedTuple):
    """One of v3's subcommands: its description and its options, with v3's base texts."""

    description: str
    # Each parameter of the callback, with v3's option name and description.
    options: dict[str, tuple[str, str]]


ROOT = "dynamic-voice-channel"  # v3's command, and the root of its register.yaml keys
# v3's subcommands, in v3's order, with the texts of Register.kt.
SUBCOMMANDS = {
    "bind": SubcommandSpec(
        "bind a voice channel",
        {
            "channel": ("channel", "voice channel to bind"),
            "format_name_1": ("format-name-1", "format name 1"),
            "format_name_2": ("format-name-2", "format name 2"),
        },
    ),
    "unbind": SubcommandSpec(
        "unbind a voice channel", {"channel": ("channel", "voice channel to unbind")}
    ),
}


class DynamicVoiceChannel(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates

    def command(self) -> app_commands.Group:
        """Build v3's ``/dynamic-voice-channel``, localized from ``register.yaml``.

        As in v3, only administrators see it by default; there is no other check. The group is
        built here, so its module is the plugin's and unloading the plugin removes it.
        """
        lang = self.lang
        group = app_commands.Group(
            name=lang.command(ROOT, f"{ROOT}.name"),
            description=lang.command("commands about dynamic voice channel", f"{ROOT}.description"),
            default_permissions=discord.Permissions(administrator=True),
        )
        group.add_command(self._subcommand("bind", self.bind_lobby))
        group.add_command(self._subcommand("unbind", self.unbind_lobby))
        return group

    def _subcommand(
        self, name: str, callback: Callable[..., Coroutine[Any, Any, None]]
    ) -> app_commands.Command[Any, ..., None]:
        """Build v3's subcommand ``name`` with ``callback``, the cog's bound method."""
        lang, spec = self.lang, SUBCOMMANDS[name]
        key = f"{ROOT}.subcommands.{name}"
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command(name, f"{key}.name"),
            description=lang.command(spec.description, f"{key}.description"),
            callback=callback,
        )
        # One call each: describe gives every option it does not name an ellipsis as its text.
        app_commands.rename(
            **{
                parameter: lang.command(option, f"{key}.options.{option}.name")
                for parameter, (option, _) in spec.options.items()
            }
        )(command)
        return app_commands.describe(
            **{
                parameter: lang.command(text, f"{key}.options.{option}.description")
                for parameter, (option, text) in spec.options.items()
            }
        )(command)

    async def bind_lobby(
        self,
        interaction: discord.Interaction,
        channel: app_commands.Transform[app_commands.AppCommandChannel, VoiceChannelOption],
        format_name_1: str,
        format_name_2: str,
    ) -> None:
        """Bind ``channel``'s category and name as a lobby with the room formats (v3's ``bind``).

        A binding of the same category and name is replaced; v3 added a duplicate. The reply is
        ``bind-success``, or ``must-under-category`` for a channel outside a category, where
        nothing is stored.
        """
        guild = interaction.guild
        if guild is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        if channel.category_id is None:
            await self._reply(interaction, "must-under-category")
            return
        binding = Binding(channel.category_id, channel.name, format_name_1, format_name_2)
        await bind(self.store, guild.id, binding)
        logger.info(
            "DynamicVoiceChannel bound the lobby %r of category %s in guild %s",
            channel.name,
            channel.category_id,
            guild.id,
        )
        await self._reply(interaction, "bind-success")

    async def unbind_lobby(
        self,
        interaction: discord.Interaction,
        channel: app_commands.Transform[app_commands.AppCommandChannel, VoiceChannelOption],
    ) -> None:
        """Remove the bindings of ``channel``'s category and current name (v3's ``unbind``).

        The reply is ``unbind-success``, ``unbind-fail`` when there was no such binding, or
        ``must-under-category`` for a channel outside a category.
        """
        guild = interaction.guild
        if guild is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        if channel.category_id is None:
            await self._reply(interaction, "must-under-category")
            return
        removed = await unbind(self.store, guild.id, channel.category_id, channel.name)
        if removed:
            logger.info(
                "DynamicVoiceChannel unbound the lobby %r of category %s in guild %s",
                channel.name,
                channel.category_id,
                guild.id,
            )
        await self._reply(interaction, "unbind-success" if removed else "unbind-fail")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Give a member who joins a lobby alone a room of their own (v3's voice update)."""
        raise NotImplementedError

    async def _reply(self, interaction: discord.Interaction, key: str) -> None:
        """Edit the deferred response into the message ``key``, in the user's locale, as v3.

        The values are v3's ``Placeholder.get(event)``, which threw outside text channels.
        """
        template = self.templates.message(key, interaction.locale.value)
        message = render_message(template, placeholder_values(interaction))
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )
