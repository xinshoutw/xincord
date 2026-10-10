"""The command, the builder, the post's buttons and the automatic draw.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:44-633
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:16-380
"""

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import global_values
from xincord.core.templates import render_message

from .model import Draft
from .texts import Texts, language, preview

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .config import Config

# v3's fields in v3's order, all text, and v3's prefix, so that v3's posts keep working.
IDS = ComponentIds("giveaway", ("action", "sub_action", "giveaway_id"), legacy_prefix="giveaway@")


@dataclass(frozen=True)
class Session:
    """A user's draft in a guild and the builder message that shows it."""

    message_id: int
    draft: Draft


class Giveaway(commands.Cog):
    """The plugin's state, handlers and loop; ``setup`` registers them."""

    def __init__(
        self, bot: commands.Bot, config: Config, store: Store, lang: Lang, templates: Templates
    ) -> None:
        """Keep the bot, the config, the store and what ``setup`` loaded."""
        self.bot = bot
        self.config = config
        self.store = store
        self.lang = lang
        self.templates = templates
        # The winners' draws: the operating system's randomness, never a seeded generator.
        self.random: random.Random = random.SystemRandom()
        # Each user's draft per guild, by user ID and guild ID; v3's StepManager.steps.
        self.drafts: dict[tuple[int, int], Session] = {}

    def command(self) -> app_commands.Command[Any, ..., None]:
        """Build v3's ``/create-giveaway``, localized from ``register.yaml``.

        A guild command without options that only administrators see by default, as in v3;
        confirming a draft checks Administrator again.
        """
        lang = self.lang
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("create-giveaway", "create_giveaway.name"),
            description=lang.command(
                "Create a giveaway with step-by-step setup", "create_giveaway.description"
            ),
            callback=self.create_giveaway,
        )
        return app_commands.default_permissions(administrator=True)(command)

    async def create_giveaway(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the builder of a new draft for the user.

        The draft replaces one the user had in the guild, as v3's; only the new builder message
        drives it. The command tree deferred the response ephemerally, as v3's core did.
        """
        guild_id = interaction.guild_id
        if guild_id is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        draft = Draft()
        message = self._builder(interaction, draft)
        shown = await interaction.edit_original_response(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )
        self.drafts[interaction.user.id, guild_id] = Session(shown.id, draft)

    def _builder(self, interaction: discord.Interaction, draft: Draft) -> Message:
        """v3's ``create-giveaway`` with the preview of ``draft``, in the user's language.

        v3 rendered it without a substitutor: v3's global values.
        """
        locale = language(self.lang, interaction.locale.value)
        embed = preview(draft, Texts(self.lang, locale), self.config.zone)
        return render_message(
            self.templates.message("create-giveaway", locale),
            global_values(interaction.client),
            build_id=IDS.build,
            models={"ga@preview-embed": embed},
        )
