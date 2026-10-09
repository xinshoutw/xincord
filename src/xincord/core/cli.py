"""The ``xincord`` command: start the bot from the working directory.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/Main.kt:17-39
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/Arguments.kt:11-60
"""

import argparse
import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from collections.abc import Sequence

LEVELS = logging.getLevelNamesMapping()


@dataclass(frozen=True)
class Options:
    """The parsed command line."""

    token: str | None = None
    level: str = "INFO"
    no_online: bool = False
    force_lang: bool = False


def parse_args(argv: Sequence[str] | None = None) -> Options:
    """Parse the command line; print a usage message and exit with status 2 if it is invalid."""
    parser = argparse.ArgumentParser(prog="xincord", description="Run the xincord Discord bot.")
    parser.add_argument("-t", "--token", help="the bot token; overrides token in config.yaml")
    parser.add_argument(
        "-l", "--level", type=str.upper, choices=sorted(LEVELS), default="INFO", help="log level"
    )
    parser.add_argument(
        "-N",
        "--no-online",
        action="store_true",
        help="load the config and the plugins without connecting, then exit",
    )
    parser.add_argument(
        "-Flang",
        "--force-renew-lang-resources",
        dest="force_lang",
        action="store_true",
        help="overwrite the exported lang files with the bundled ones",
    )
    return Options(**vars(parser.parse_args(argv)))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bot with the command line ``argv`` and return the exit status."""
    options = parse_args(argv)
    discord.utils.setup_logging(level=LEVELS[options.level])
    return asyncio.run(run(options))


async def run(options: Options) -> int:
    """Start the bot from the working directory and return the exit status once it stops."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
