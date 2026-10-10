"""The settings menu, its components, the voice and status listeners and the checks at READY.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:29-439
"""

import re
from typing import TYPE_CHECKING, cast

from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

from .settings import list_text
from .store import add_channels, read_setting, remove, toggle

if TYPE_CHECKING:
    from collections.abc import Mapping

    import discord

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .settings import Setting
    from .store import Kind

# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("voice_logger", ("action",), legacy_prefix="voice-logger@")
MENU = "voice-logger@setting"  # the settings menu's template
BUTTON = 2  # the component type of a button
ENTITY_SELECTS = frozenset({5, 6, 7, 8})  # user, role, mentionable and channel select menus
# The buttons that show a list's select menu, and the select menus that add to a list.
SELECTS = {"modify_allow_btn": "modify-allow", "modify_block_btn": "modify-block"}
MENUS: dict[str | None, Kind] = {"modify_allow_menu": "allow", "modify_block_menu": "block"}
SNOWFLAKE = re.compile(r"[0-9]+")


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

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Send a press or a choice in the settings menu to its handler; ``setup`` routes here.

        As v3's two handlers, buttons take the button actions and entity select menus the select
        actions, in v3's ID format too; anything else gets no response (v3 threw for an unknown
        select action). Each answer replaces the menu's whole message, as JDA's
        ``MessageEditData.fromCreateData`` did; v3's ``deferEdit`` and edit became one request.
        """
        where = _where(interaction)
        if where is None:  # the menu exists in guilds only
            return
        data = cast("Mapping[str, object]", interaction.data or {})
        kind, action = data.get("component_type"), parsed.fields.get("action")
        if kind == BUTTON:
            await self._press(interaction, where, action)
        elif kind in ENTITY_SELECTS and action in MENUS:
            ids = _ids(data.get("values"))
            setting = await add_channels(self.store, *where, MENUS[action], ids)
            await _edit(interaction, self._menu(interaction, setting))

    async def _press(
        self, interaction: discord.Interaction, where: tuple[int, int], action: str | None
    ) -> None:
        """Toggle the mode, show a list's select menu, or delete the settings, as v3's buttons."""
        if action == "toggle_btn":
            await _edit(interaction, self._menu(interaction, await toggle(self.store, *where)))
        elif action in SELECTS:
            await _edit(interaction, self._render(interaction, SELECTS[action]))
        elif action == "delete_btn":
            await remove(self.store, *where)
            await _edit(interaction, self._render(interaction, "delete"))

    def _render(self, interaction: discord.Interaction, name: str) -> Message:
        """Template ``name`` in the user's locale with v3's ``Placeholder.get(event)``."""
        template = self.templates.message(name, interaction.locale.value)
        return render_message(template, placeholder_values(interaction), build_id=IDS.build)

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


async def _edit(interaction: discord.Interaction, message: Message) -> None:
    """Replace the component's whole message with ``message``."""
    await interaction.response.edit_message(
        content=message.content,
        embeds=message.embeds,
        view=message.view,
        attachments=message.files,
    )


def _ids(values: object) -> list[int]:
    """The channel and category IDs that a select menu sent, as Discord's decimal strings."""
    entries = cast("list[object]", values) if isinstance(values, list) else []
    return [
        int(entry) for entry in entries if isinstance(entry, str) and SNOWFLAKE.fullmatch(entry)
    ]


def _where(interaction: discord.Interaction) -> tuple[int, int] | None:
    """The guild and the channel of ``interaction``, the listen channel's place, if in a guild."""
    guild_id, channel_id = interaction.guild_id, interaction.channel_id
    return None if guild_id is None or channel_id is None else (guild_id, channel_id)
