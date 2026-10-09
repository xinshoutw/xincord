"""The example command and its counter button.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/_Example.kt:11-43
"""

from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import actor_values, interaction_values
from xincord.core.templates import render_message

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config

# Button IDs: example:1:a=<action>;b=<count>. A ported plugin lists its v3 fields first, in v3
# order, and passes legacy_prefix (and legacy_hex); _Example had no components in v3.
IDS = ComponentIds("example", ("action", "count"))
NONE = "none"  # the text of an omitted option2, as in v3


class Example(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.config = config
        self.lang = lang
        self.templates = templates

    async def reply(
        self, interaction: discord.Interaction, option1: str, option2: int | None
    ) -> None:
        """Turn the deferred response into the example embed above a counter at 0."""
        values = placeholder_values(interaction) | {
            "_Example@option1": option1,
            "_Example@option2": NONE if option2 is None else str(option2),
            "_Example@example_key": self.config.example_key,
            "_Example@count": "0",
        }
        locale = interaction.locale.value
        reply = render_message(self.templates.message("example", locale), values)
        counter = render_message(
            self.templates.message("counter", locale), values, build_id=IDS.build
        )
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=reply.content, embeds=reply.embeds, view=counter.view
        )


def placeholder_values(interaction: discord.Interaction) -> dict[str, str]:
    """Return v3's ``Placeholder.get(event)``: the acting user's keys and the interaction's."""
    bot = interaction.client.user  # set once the bot has logged in
    actor = {} if bot is None else actor_values(interaction.user, bot)
    return actor | interaction_values(interaction)
