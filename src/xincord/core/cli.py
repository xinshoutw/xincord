"""The ``xincord`` command: start the bot from the working directory.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/Main.kt:17-39
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/Arguments.kt:11-60
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class Options:
    """The parsed command line."""

    token: str | None = None
    level: str = "INFO"
    no_online: bool = False
    force_lang: bool = False


def parse_args(argv: Sequence[str] | None = None) -> Options:
    """Parse the command line; print a usage message and exit with status 2 if it is invalid."""
    raise NotImplementedError


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bot with the command line ``argv`` and return the exit status."""
    raise NotImplementedError


async def run(options: Options) -> int:
    """Start the bot from the working directory and return the exit status once it stops."""
    raise NotImplementedError
