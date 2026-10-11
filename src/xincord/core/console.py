"""The interactive console: ``reload [plugin]`` and the stop words.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:12-94
"""

import logging
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.shortcuts import CompleteStyle

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.completion import Completer

    from xincord.core.bot import Bot

logger = logging.getLogger(__name__)

PROMPT = "console > "
STOP_WORDS = ("stop", "exit", "shutdown")


def completer(bot: Bot) -> Completer:
    """Complete the command names and, after ``reload``, the loaded plugins."""
    return NestedCompleter.from_nested_dict(
        {"reload": dict.fromkeys(bot.loaded), **dict.fromkeys(STOP_WORDS)}
    )


async def run_console(bot: Bot, stop: Callable[[], None]) -> None:
    """Read commands until a stop word or end of input, then call ``stop``."""
    # Matches are listed above the prompt, so no lines stay free below it: under compose the
    # terminal's output is the container's log.
    session: PromptSession[str] = PromptSession(complete_style=CompleteStyle.READLINE_LIKE)
    while True:
        try:
            # Rebuilt each time, so plugins loaded by a reload complete too.
            line = await session.prompt_async(PROMPT, completer=completer(bot))
        except KeyboardInterrupt:
            logger.info("Interrupted by user: ^C")
            continue
        except EOFError:
            logger.info("Interrupted by user: ^D")
            break
        command, *args = line.split() or [""]
        match command.lower(), args:
            case "", _:
                pass
            case "reload", []:
                await bot.reload()
            case "reload", [plugin]:
                await bot.reload(plugin)
            case word, [] if word in STOP_WORDS:
                break
            case _:
                logger.warning("Unknown command: %s", line.strip())
    stop()
