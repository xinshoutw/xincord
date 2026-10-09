"""The interaction log: a console line per interaction and lines in configured channels.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-65
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/consolelogger/ConsoleLogger.kt:91-139
"""

import logging
from typing import TYPE_CHECKING, cast

import discord

from xincord.core.placeholders import actor_values, interaction_values, render

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xincord.core.config import InteractionLogTarget

logger = logging.getLogger(__name__)

# Slash and message commands by command type; user commands are not logged, as in v3.
COMMAND_KINDS: dict[object, str] = {1: "CMD", 3: "MSG"}
COMPONENT_KINDS: dict[object, str] = {2: "BTN", 3: "STRING"}  # the other selects are ENTITY
TARGET_TYPES = {"CMD": "command", "BTN": "button", "MODAL": "modal"}  # what log channels take


def describe(interaction: discord.Interaction) -> tuple[str, str] | None:
    """Return v3's kind and text for an interaction that is logged, or None."""
    data = cast("Mapping[str, object]", interaction.data or {})
    match interaction.type:
        case discord.InteractionType.application_command:
            if (kind := COMMAND_KINDS.get(data.get("type"))) is None:
                return None
            return kind, interaction_values(interaction)["command_string"]
        case discord.InteractionType.component:
            kind = COMPONENT_KINDS.get(data.get("component_type"), "ENTITY")
            return kind, str(data.get("custom_id", ""))
        case discord.InteractionType.modal_submit:
            return "MODAL", str(data.get("custom_id", ""))
        case _:
            return None


async def log(
    client: discord.Client,
    interaction: discord.Interaction,
    targets: Sequence[InteractionLogTarget],
) -> None:
    """Log the interaction to the console and to the targets that take its kind."""
    if (described := describe(interaction)) is None:
        return
    kind, text = described
    logger.info("[%s] %s: %s", kind, interaction.user.name, text)
    channel_type = TARGET_TYPES.get(kind)
    matching = [target for target in targets if channel_type in target.types]
    if not matching or client.user is None:
        return
    values = (
        actor_values(interaction.user, client.user)
        | interaction_values(interaction)
        | {"cl_type": kind, "cl_interaction_string": text}
    )
    for target in matching:
        channel = client.get_partial_messageable(target.channel_id, guild_id=target.guild_id)
        try:
            await channel.send(
                render(target.format, values), allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.HTTPException:
            logger.exception("Posting to interaction log channel %s failed", target.channel_id)
