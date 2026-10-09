"""The interactive console: ``reload [plugin]`` and the stop words.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:12-94
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.completion import Completer

    from xincord.core.bot import Bot

PROMPT = "console > "
STOP_WORDS = ("stop", "exit", "shutdown")


def completer(bot: Bot) -> Completer:
    """Complete the command names and, after ``reload``, the loaded plugins."""
    raise NotImplementedError


async def run_console(bot: Bot, stop: Callable[[], None]) -> None:
    """Read commands until a stop word or end of input, then call ``stop``."""
    raise NotImplementedError
