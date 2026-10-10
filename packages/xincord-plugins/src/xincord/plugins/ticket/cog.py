"""The commands, the builder, the panels, the ticket channels and their control row.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:56-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:17-332
"""

import logging
from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.component_ids import ComponentIds

from .texts import Texts

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

logger = logging.getLogger(__name__)

# v3's fields in v3's order, the user ID in hex as v3 wrote it, and v3's prefix, so that v3's
# panels and ticket channels keep working.
IDS = ComponentIds(
    "ticket",
    ("action", "sub_action", "color_index", "user_id", "msg_id", "btn_index"),
    legacy_prefix="ticket@",
    legacy_hex=("user_id",),
)


class Ticket(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.templates = templates

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
