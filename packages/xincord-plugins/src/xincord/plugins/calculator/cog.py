"""The /basic-calculate command and its replies."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.placeholders import actor_values
from xincord.core.templates import render_message

from .calculator import FORMULA_MAX, CalcError, calculate, normalize

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xincord.core.i18n import Lang
    from xincord.core.templates import Message, Templates

logger = logging.getLogger(__name__)


@runtime_checkable
class Postable(Protocol):
    """A channel that takes messages; forums and categories do not."""

    async def send(
        self, *, content: str | None = None, embeds: Sequence[discord.Embed] = ...
    ) -> object:
        """Send a message to the channel."""
        ...


class Calculator(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, lang: Lang, templates: Templates) -> None:
        """Keep what ``setup`` loaded."""
        self.lang = lang
        self.templates = templates

    def command(self) -> app_commands.Command[Any, ..., None]:
        """Build ``/basic-calculate``, localized from ``register.yaml``."""
        lang = self.lang
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("basic-calculate", "basic-calculate.name"),
            description=lang.command(
                "calculate + - * / ^ ( ) math problem", "basic-calculate.description"
            ),
            callback=self.basic_calculate,
        )
        app_commands.rename(
            formula=lang.command("formula", "basic-calculate.options.formula.name")
        )(command)
        return app_commands.describe(
            formula=lang.command("What's problem?", "basic-calculate.options.formula.description")
        )(command)

    async def basic_calculate(
        self,
        interaction: discord.Interaction,
        formula: app_commands.Range[str, None, FORMULA_MAX],
    ) -> None:
        """Post the answer to the channel and delete the deferred response.

        On an error, edit the deferred response into the error instead.
        """
        question = normalize(formula)
        values = _values(interaction) | {"bc_question": question}
        try:
            # A worker thread, so that a long calculation never holds up the gateway.
            answer = await asyncio.to_thread(calculate, question)
        except CalcError as error:
            await self._reply_error(interaction, values | {"bc_error": str(error)})
            return
        values |= {"bc_answer": answer, "bc_answer_round": _whole_part(answer)}
        message = self.templates.message("basic-calculate", interaction.locale.value)
        await _post(interaction, render_message(message, values))

    async def _reply_error(self, interaction: discord.Interaction, values: dict[str, str]) -> None:
        """Turn the deferred ephemeral response into the error template, as v3 did."""
        message = self.templates.message("error", interaction.locale.value)
        reply = render_message(message, values)
        await interaction.edit_original_response(content=reply.content, embeds=reply.embeds)


async def _post(interaction: discord.Interaction, reply: Message) -> None:
    """Send ``reply`` to the channel, as v3 did, or else into the deferred response."""
    channel = interaction.channel
    if isinstance(channel, Postable):
        try:
            await channel.send(content=reply.content or None, embeds=reply.embeds)
        except discord.HTTPException as error:
            logger.warning(
                "Calculator cannot post in %r, so it answers privately: %s", channel, error
            )
        else:
            await interaction.delete_original_response()
            return
    await interaction.edit_original_response(content=reply.content, embeds=reply.embeds)


def _values(interaction: discord.Interaction) -> dict[str, str]:
    """v3's ``Placeholder.get(member)``: the member's keys and the bot's."""
    bot = interaction.client.user  # set once the bot has logged in
    return {} if bot is None else actor_values(interaction.user, bot)


def _whole_part(answer: str) -> str:
    """The digits before the decimal point; v3 meant this, but its split kept the whole answer."""
    whole = answer.partition(".")[0]
    return "0" if whole == "-0" else whole
