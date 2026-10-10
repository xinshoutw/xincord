"""The example command and its counter button.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/_Example.kt:11-43
"""

from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

if TYPE_CHECKING:
    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config

# Button IDs: example:1:a=<action>;b=<count>. A ported plugin lists its v3 fields first, in v3
# order, and passes legacy_prefix (and legacy_hex); _Example had no components in v3.
IDS = ComponentIds("example", ("action", "count"))
NONE = "none"  # the text of an omitted option2, as in v3
OPTION1_MAX = 1024  # Discord's limit for an embed field's value


class Example(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.config = config
        self.lang = lang
        self.templates = templates

    def command(self) -> app_commands.Command[Any, ..., None]:
        """Build ``/example-command``, localized from ``register.yaml``.

        The Lang loads in ``setup``, so commands are built there instead of with
        ``@app_commands.command``. Given a bound method, discord.py makes this cog the command's
        binding, as for a decorated cog command.
        """
        lang = self.lang
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("example-command", "example.name"),
            description=lang.command("this is an example command", "example.description"),
            callback=self.example_command,
        )
        app_commands.rename(
            option1=lang.command("option1", "example.options.option1.name"),
            option2=lang.command("option2", "example.options.option2.name"),
        )(command)
        return app_commands.describe(
            option1=lang.command(
                "this is an example option", "example.options.option1.description"
            ),
            option2=lang.command(
                "this is an example option", "example.options.option2.description"
            ),
        )(command)

    async def example_command(
        self,
        interaction: discord.Interaction,
        option1: app_commands.Range[str, None, OPTION1_MAX],
        option2: int | None = None,
    ) -> None:
        """Turn the deferred response into the example embed above a counter at 0."""
        values = self._values(interaction, 0) | {
            "_Example@option1": option1,
            "_Example@option2": NONE if option2 is None else str(option2),
        }
        locale = interaction.locale.value
        reply = render_message(self.templates.message("example", locale), values)
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=reply.content, embeds=reply.embeds, view=self._counter(locale, values)
        )

    async def count(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Show one press more on the button; ``setup`` routes the IDs of ``IDS`` here."""
        if parsed.fields.get("action") != "count":
            return
        values = self._values(interaction, int(parsed.fields["count"]) + 1)
        # Editing only the view keeps the embed above it.
        await interaction.response.edit_message(
            view=self._counter(interaction.locale.value, values)
        )

    def _values(self, interaction: discord.Interaction, count: int) -> dict[str, str]:
        """Return the placeholder values that both templates can use.

        ``placeholder_values`` is v3's ``Placeholder.get(event)``: the acting user's keys and the
        interaction's.
        """
        return placeholder_values(interaction) | {
            "_Example@example_key": self.config.example_key,
            "_Example@count": str(count),
        }

    def _counter(
        self, locale: str, values: dict[str, str]
    ) -> discord.ui.View | discord.ui.LayoutView | None:
        """Render the counter button; its ID carries the count."""
        message = self.templates.message("counter", locale)
        return render_message(message, values, build_id=IDS.build).view
