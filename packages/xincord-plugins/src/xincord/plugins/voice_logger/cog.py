"""The settings menu, its components, the voice and status listeners and the checks at READY.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:29-439
"""

from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

from .settings import list_text
from .store import read_setting

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .settings import Setting

# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("voice_logger", ("action",), legacy_prefix="voice-logger@")
MENU = "voice-logger@setting"  # the settings menu's template


class VoiceLogger(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the current channel's settings menu (v3's ``setting``).

        Nothing is written: a channel without settings shows v3's default, the allow mode with
        empty lists. The command works in every channel; v3's ``Placeholder.get(event)`` threw
        outside text channels.
        """
        where = _where(interaction)
        if where is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        message = self._menu(interaction, await read_setting(self.store, *where))
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )

    def _menu(self, interaction: discord.Interaction, setting: Setting) -> Message:
        """v3's settings menu for ``setting``, in the user's locale.

        The values are v3's ``Placeholder.get(event)``, the mode and both lists, each in the
        locale's line format from ``placeholder.yaml``.
        """
        locale = interaction.locale.value
        values = placeholder_values(interaction)
        empty = self.lang.text("placeholder.empty", locale)
        lists = {
            f"vl_{kind}_list_format": list_text(
                ids,
                self.lang.text(f"placeholder.{kind}_list_format", locale),
                empty,
                values,
                f"{kind}list",
            )
            for kind, ids in (("allow", setting.allow), ("block", setting.block))
        }
        mode = {"vl_channel_mode": "ALLOW" if setting.allow_mode else "BLOCK"}
        template = self.templates.message(MENU, locale)
        return render_message(template, values | mode | lists, build_id=IDS.build)


def _where(interaction: discord.Interaction) -> tuple[int, int] | None:
    """The guild and the channel of ``interaction``, the listen channel's place, if in a guild."""
    guild_id, channel_id = interaction.guild_id, interaction.channel_id
    return None if guild_id is None or channel_id is None else (guild_id, channel_id)
