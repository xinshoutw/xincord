"""The interaction log: a console line per interaction and lines in configured channels.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-65
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/consolelogger/ConsoleLogger.kt:91-139
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from xincord.core.config import InteractionLogTarget


def describe(interaction: discord.Interaction) -> tuple[str, str] | None:
    """Return v3's kind and text for an interaction that is logged, or None."""
    raise NotImplementedError


async def post(
    client: discord.Client,
    interaction: discord.Interaction,
    kind: str,
    text: str,
    targets: Sequence[InteractionLogTarget],
) -> None:
    """Send the interaction's line to the targets that log its kind."""
    raise NotImplementedError
