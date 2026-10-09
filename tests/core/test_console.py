"""The interactive console.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:12-94
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from xincord.core.bot import Bot
from xincord.core.console import completer, run_console

if TYPE_CHECKING:
    from pathlib import Path

    from plugin_fakes import FakePlugins
    from xincord.core.storage import Store

SETUP = "async def setup(bot):\n    pass\n"
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
    bot = Bot([], root=tmp_path, store=store)

    stops = await typed(bot, "reload\nRELOAD Alpha\n\n  \nfrobnicate now\nstop\n")

    assert reloads == [None, "Alpha"]
    assert "Unknown command: frobnicate now" in caplog.text
    assert stops == 1


@pytest.mark.parametrize("keys", ["stop\n", "EXIT\n", "shutdown\n", CTRL_D])
async def test_stopping(store: Store, tmp_path: Path, reloads: list[str | None], keys: str) -> None:
    """Requirement: Console commands."""
    bot = Bot([], root=tmp_path, store=store)

    stops = await typed(bot, keys + "reload\n")

    assert stops == 1
    assert reloads == []  # nothing after the stop is read


async def test_interrupt(
    store: Store, tmp_path: Path, reloads: list[str | None], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Console commands."""
    caplog.set_level(logging.INFO)
    bot = Bot([], root=tmp_path, store=store)

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
