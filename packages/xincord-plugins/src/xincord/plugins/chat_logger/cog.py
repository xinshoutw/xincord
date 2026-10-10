"""The command, the menu's components, the message listeners and the checks at READY.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:31-382
"""

from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.plugins.listen_channels.menu import ListenChannels, Menu
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .config import Config

NAMESPACE = "ChatLogger"  # the plugin's name: its settings in the store
# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("chat_logger", ("action",), legacy_prefix="chat-logger@")
ROOT = "chat-logger"  # v3's command, and the root of its register.yaml keys
MENU = "chat-logger@setting"  # the settings menu's template


class ChatLogger(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(
        self, bot: commands.Bot, config: Config, store: Store, lang: Lang, templates: Templates
    ) -> None:
        """Keep the bot, the config, the store and what ``setup`` loaded."""
        self.bot = bot
        self.config = config
        self.store = store
        self.lang = lang
        self.settings = ListenSettings(store, NAMESPACE)
        # The menu, its components, the posts and the checks at READY, shared with VoiceLogger.
        self.listen = ListenChannels(bot, self.settings, Menu(lang, templates, IDS, "cl", MENU))

    def command(self) -> app_commands.Group:
        """Build v3's ``/chat-logger`` with its subcommand ``setting``, from ``register.yaml``.

        As in v3, only administrators see it by default; there is no other check. The group is
        built here, so its module is the plugin's and unloading the plugin removes it.
        """
        lang = self.lang
        group = app_commands.Group(
            name=lang.command(ROOT, f"{ROOT}.name"),
            description=lang.command("commands about chat logger", f"{ROOT}.description"),
            default_permissions=discord.Permissions(administrator=True),
        )
        key = f"{ROOT}.subcommands.setting"
        setting: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("setting", f"{key}.name"),
            description=lang.command("set chat log in this channel", f"{key}.description"),
            callback=self.show_settings,
        )
        group.add_command(setting)
        return group

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the channel's settings menu (v3's ``setting``)."""
        await self.listen.show(interaction)

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Change the settings from the menu's buttons and select menus; ``setup`` routes here."""
        await self.listen.handle(interaction, parsed)
