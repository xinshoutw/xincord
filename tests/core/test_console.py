"""The interactive console.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:12-94
"""

import asyncio
import io
import logging
import re
import signal
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

import discord
import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.data_structures import Size
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.output.vt100 import Vt100_Output

from plugin_fakes import until, watch_closes, write_config
from xincord.core import cli
from xincord.core.bot import Bot
from xincord.core.cli import Options, main, run
from xincord.core.console import completer, run_console

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from plugin_fakes import FakePlugins
    from xincord.core.storage import Store

SETUP = "async def setup(bot):\n    pass\n"
RECORD = """
from .. import calls


async def setup(bot):
    calls.append("setup Alpha")


async def teardown(bot):
    calls.append("teardown Alpha")
"""
CTRL_C = "\x03"
CTRL_D = "\x04"


async def typed(bot: Bot, keys: str) -> int:
    """Run the console on ``keys`` as keyboard input; return how often it asked to stop."""
    stops: list[None] = []
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        pipe.send_text(keys)
        async with asyncio.timeout(5):
            await run_console(bot, lambda: stops.append(None))
    return len(stops)


@pytest.fixture
def reloads(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    """Record the plugins that ``Bot.reload`` is called with."""
    calls: list[str | None] = []

    async def reload(_self: Bot, plugin: str | None = None) -> str:
        calls.append(plugin)
        return "Reloaded: none."

    monkeypatch.setattr(Bot, "reload", reload)
    return calls


async def test_reload_commands(
    store: Store, tmp_path: Path, reloads: list[str | None], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Console commands."""
    caplog.set_level(logging.INFO)
    bot = Bot([], root=tmp_path, data=tmp_path / "data", store=store)

    stops = await typed(bot, "reload\nRELOAD Alpha\n\n  \nfrobnicate now\nstop\n")

    assert reloads == [None, "Alpha"]
    assert "Unknown command: frobnicate now" in caplog.text
    assert stops == 1


@pytest.mark.parametrize("keys", ["stop\n", "EXIT\n", "shutdown\n", CTRL_D])
async def test_stopping(store: Store, tmp_path: Path, reloads: list[str | None], keys: str) -> None:
    """Requirement: Console commands."""
    bot = Bot([], root=tmp_path, data=tmp_path / "data", store=store)

    stops = await typed(bot, keys + "reload\n")

    assert stops == 1
    assert reloads == []  # nothing after the stop is read


async def test_interrupt(
    store: Store, tmp_path: Path, reloads: list[str | None], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Console commands."""
    caplog.set_level(logging.INFO)
    bot = Bot([], root=tmp_path, data=tmp_path / "data", store=store)

    stops = await typed(bot, CTRL_C + "reload\nstop\n")

    assert "Interrupted by user: ^C" in caplog.text
    assert reloads == [None]
    assert stops == 1


async def test_completing(fake_plugins: FakePlugins, store: Store, tmp_path: Path) -> None:
    """Requirement: Console completion."""
    fake_plugins.add("Alpha", SETUP)
    fake_plugins.add("Beta", SETUP)
    bot = fake_plugins.bot(["Alpha", "Beta"], tmp_path / "plugins", store)
    assert await bot.load_plugins() == []

    def offered(text: str) -> list[str]:
        events = completer(bot).get_completions(Document(text), CompleteEvent())
        return [completion.text for completion in events]

    assert offered("re") == ["reload"]
    assert offered("s") == ["stop", "shutdown"]
    assert offered("reload A") == ["Alpha"]


async def test_no_space_kept_for_a_menu(store: Store, tmp_path: Path) -> None:
    """Requirement: Console completion."""
    bot = Bot([], root=tmp_path, data=tmp_path / "data", store=store)
    screen = io.StringIO()
    terminal = Vt100_Output(screen, lambda: Size(rows=24, columns=80), enable_cpr=False)

    with create_pipe_input() as pipe, create_app_session(input=pipe, output=terminal):
        pipe.send_text("stop\r")
        async with asyncio.timeout(5):
            await run_console(bot, lambda: None)
    shown = screen.getvalue()

    assert "console > " in shown
    assert shown.count("\n") == 1  # the line feed after the accepted input
    assert re.search(r"\x1b\[\d*A", shown) is None


class Terminal:
    def __init__(self, *, tty: bool) -> None:
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


@pytest.mark.parametrize(
    ("argv", "tty", "console"), [([], True, True), ([], False, False), (["-N"], True, False)]
)
def test_terminal_detection(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    tty: bool,  # noqa: FBT001
    console: bool,  # noqa: FBT001
) -> None:
    """Requirement: Console only on a terminal."""
    events: list[str] = []

    @contextmanager
    def patch_stdout(*, raw: bool) -> Generator[None]:
        events.append(f"patch raw={raw}")
        yield
        events.append("unpatch")

    def setup_logging(*, level: int) -> None:
        events.append(f"logging {level}")

    async def fake_run(_options: Options, *, console: bool = False) -> int:
        events.append(f"run console={console}")
        return 0

    monkeypatch.setattr(sys, "stdin", Terminal(tty=tty))
    monkeypatch.setattr(sys, "stdout", Terminal(tty=tty))
    monkeypatch.setattr(cli, "patch_stdout", patch_stdout)
    monkeypatch.setattr(discord.utils, "setup_logging", setup_logging)
    monkeypatch.setattr(cli, "run", fake_run)

    assert main(argv) == 0
    if console:
        assert events == ["patch raw=True", "logging 20", "run console=True", "unpatch"]
    else:
        assert events == ["logging 20", "run console=False"]


@pytest.mark.parametrize(
    "tty",
    [
        pytest.param(
            False,
            marks=pytest.mark.xfail(
                strict=True, raises=KeyError, reason="Plain log lines off a terminal"
            ),
        ),
        True,
    ],
)
def test_plain_log_lines_off_a_terminal(monkeypatch: pytest.MonkeyPatch, tty: bool) -> None:  # noqa: FBT001
    """Requirement: Plain log lines off a terminal.

    discord.py colours its lines inside any Docker container; without a terminal they stay plain.
    """
    setups: list[dict[str, object]] = []

    def setup_logging(**options: object) -> None:
        setups.append(options)

    async def fake_run(_options: Options, *, console: bool = False) -> int:  # noqa: ARG001
        return 0

    monkeypatch.setattr(sys, "stderr", Terminal(tty=tty))
    monkeypatch.setattr(discord.utils, "setup_logging", setup_logging)
    monkeypatch.setattr(cli, "run", fake_run)

    assert main(["-N"]) == 0
    (options,) = setups
    if tty:
        assert "formatter" not in options  # discord.py's colour formatter
        return
    formatter = options["formatter"]
    assert isinstance(formatter, logging.Formatter)
    record = logging.LogRecord(
        "xincord.core.bot", logging.INFO, __file__, 1, "Bot ready", None, None
    )
    line = formatter.format(record)
    time = r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d"
    assert re.fullmatch(time + r" INFO     xincord\.core\.bot Bot ready", line)
    assert chr(27) not in line  # ESC, which starts every colour code


@pytest.mark.parametrize(("keys", "signum"), [("stop\n", None), ("", signal.SIGTERM)])
async def test_console_while_running(
    installed: FakePlugins,
    monkeypatch: pytest.MonkeyPatch,
    keys: str,
    signum: signal.Signals | None,
) -> None:
    """Requirement: Console only on a terminal."""
    installed.add("Alpha", RECORD)
    write_config("token: abc\nplugins: [Alpha]\n")
    closed = watch_closes(monkeypatch)

    async def start(self: Bot, _token: str) -> None:
        await self.setup_hook()
        if signum is not None:
            signal.raise_signal(signum)
        await until(self.is_closed)

    monkeypatch.setattr(Bot, "start", start)

    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        pipe.send_text(keys)
        async with asyncio.timeout(5):
            assert await run(Options(), console=True) == 0
    assert installed.calls() == ["setup Alpha", "teardown Alpha"]
    assert len(closed) == 1
