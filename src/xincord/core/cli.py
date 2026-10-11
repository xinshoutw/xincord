"""The ``xincord`` command: start the bot from the working directory."""

import argparse
import asyncio
import logging
import os
import signal
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from prompt_toolkit.patch_stdout import patch_stdout

from xincord.core.bot import Bot
from xincord.core.config import (
    CORE_CONFIG,
    ConfigError,
    CoreConfig,
    default_core_config,
    load_config,
)
from xincord.core.console import run_console
from xincord.core.plugins import discover
from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import Coroutine, Sequence

logger = logging.getLogger(__name__)

LEVELS = logging.getLevelNamesMapping()
PLUGINS = Path("plugins")
# The store's database and the plugins' own data files, which a container keeps in a volume.
DATA = Path("data")
DATABASE = DATA / "xincord.db"
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)
# The bot token's environment variable, which overrides config.yaml's token: never the command
# line, which every user of the host can list.
TOKEN = "XINCORD_TOKEN"  # noqa: S105 - the variable's name, not a token
# discord.py colours its log lines inside any Docker container, with a terminal or without. Off a
# terminal, as in a container's log, they stay plain, laid out as the coloured ones.
PLAIN = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s", "%Y-%m-%d %H:%M:%S")


@dataclass(frozen=True)
class Options:
    """The parsed command line."""

    level: str = "INFO"
    no_online: bool = False
    force_lang: bool = False


def parse_args(argv: Sequence[str] | None = None) -> Options:
    """Parse the command line; print a usage message and exit with status 2 if it is invalid."""
    parser = argparse.ArgumentParser(prog="xincord", description="Run the xincord Discord bot.")
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
    console = not options.no_online and sys.stdin.isatty() and sys.stdout.isatty()
    level = LEVELS[options.level]
    colour = sys.stderr.isatty()  # before the patch, whose proxy stands in for the terminal
    # Set up logging inside the patch, so log lines go through prompt_toolkit's proxy and
    # print above the prompt.
    with patch_stdout(raw=True) if console else nullcontext():
        if colour:
            discord.utils.setup_logging(level=level)
        else:
            discord.utils.setup_logging(level=level, formatter=PLAIN)
        return asyncio.run(run(options, console=console))


async def run(options: Options, *, console: bool = False) -> int:
    """Start the bot from the working directory and return the exit status once it stops.

    Args:
        options: The parsed command line.
        console: Run the interactive console while the bot runs.
    """
    try:
        config = load_config(CORE_CONFIG, CoreConfig, default_core_config())
    except ConfigError as error:
        return _failed(str(error))
    token = os.environ.get(TOKEN) or config.token
    if not (token or options.no_online):
        return _failed(f"No bot token: set {TOKEN} or token in {CORE_CONFIG}")
    store = await Store.open(DATABASE)
    try:
        plugins = discover(config.plugins)
        bot = Bot(
            plugins,
            root=PLUGINS,
            data=DATA,
            store=store,
            force_lang=options.force_lang,
            config=config,
        )
        if options.no_online:
            return await _check(bot, config.plugins)
        return await _serve(bot, token, console=console)
    finally:
        await store.close()


async def _check(bot: Bot, enabled: Sequence[str]) -> int:
    """Load the plugins without connecting; succeed if every enabled one loaded."""
    async with bot:
        await bot.setup_hook()
        missing = [name for name in enabled if name not in bot.loaded]
    if missing:
        return _failed(f"Plugins not loaded: {', '.join(missing)}")
    logger.info("The config and the plugins loaded; not connecting (--no-online)")
    return 0


async def _serve(bot: Bot, token: str, *, console: bool) -> int:
    """Run the bot until a stop signal or the console closes it; SIGHUP reloads."""
    loop = asyncio.get_running_loop()
    tasks: set[asyncio.Task[object]] = set()

    def spawn(coroutine: Coroutine[object, object, object]) -> asyncio.Task[object]:
        task = loop.create_task(coroutine)
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return task

    def stop() -> None:
        logger.info("Stopping")
        spawn(bot.close())

    for signum in STOP_SIGNALS:
        loop.add_signal_handler(signum, stop)
    loop.add_signal_handler(signal.SIGHUP, lambda: spawn(bot.reload()))
    prompt: asyncio.Task[object] | None = None
    try:
        async with bot:
            if console:
                prompt = spawn(run_console(bot, stop))
            await bot.start(token)
            await bot.close()  # wait for a close that a signal or the console started
    except (discord.LoginFailure, discord.PrivilegedIntentsRequired) as error:
        return _failed(f"Cannot connect to Discord: {error}")
    finally:
        if prompt is not None:
            prompt.cancel()  # the bot may have stopped without the console
            await asyncio.gather(prompt, return_exceptions=True)
        for signum in (*STOP_SIGNALS, signal.SIGHUP):
            loop.remove_signal_handler(signum)
    return 0


def _failed(message: str) -> int:
    logger.error("%s", message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
