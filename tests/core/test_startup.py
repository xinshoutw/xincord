"""Startup, the offline check and the stop signals.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/Main.kt:17-39
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/SettingsLoader.kt:21-33
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:36-107
"""

import asyncio
import signal
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.bot import Bot
from xincord.core.cli import Options, run
from xincord.core.i18n import Translator
from xincord.core.plugins import GROUP
from xincord.core.storage import Store

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

    from plugin_fakes import FakePlugins

PLUGIN = """
from xincord.core.config import Model

from .. import calls


class Config(Model):
    greeting: str


async def setup(bot):
    context = bot.plugin_context(__name__)
    context.config(Config)
    context.lang("en-US")
    calls.append("setup")


async def teardown(bot):
    calls.append("teardown")
"""
BUNDLE = {"config.yaml": "greeting: Hello\n", "lang/en-US/register.yaml": "greet:\n  name: greet\n"}
BROKEN = """
async def setup(bot):
    raise RuntimeError("boom")
"""


@pytest.fixture
def installed(
    fake_plugins: FakePlugins, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> FakePlugins:
    """Make the fake plugins the installed ones and work in an empty directory."""

    def entry_points(*, group: str) -> list[EntryPoint]:
        assert group == GROUP
        return fake_plugins.entry_points

    monkeypatch.setattr(metadata, "entry_points", entry_points)
    workdir = tmp_path / "bot"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return fake_plugins


def write_config(text: str) -> None:
    Path("config.yaml").write_text(text, encoding="utf-8")


def watch_closes(monkeypatch: pytest.MonkeyPatch) -> list[Store]:
    closed: list[Store] = []
    close = Store.close

    async def recording(self: Store) -> None:
        closed.append(self)
        await close(self)

    monkeypatch.setattr(Store, "close", recording)
    return closed


@pytest.mark.usefixtures("installed")
@pytest.mark.parametrize(("option", "used"), [("abc", "abc"), (None, "from-config")])
async def test_token_precedence(
    monkeypatch: pytest.MonkeyPatch, option: str | None, used: str
) -> None:
    """Requirement: Startup loads the configured plugins."""
    write_config("token: from-config\n")
    tokens: list[str] = []

    async def start(_self: Bot, token: str) -> None:
        tokens.append(token)

    monkeypatch.setattr(Bot, "start", start)

    assert await run(Options(token=option)) == 0
    assert tokens == [used]
    assert Path("data/xincord.db").is_file()


async def test_setup_before_connecting(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Startup loads the configured plugins."""
    fake_plugins.add("Alpha", PLUGIN, BUNDLE)
    bot = fake_plugins.bot(["Alpha"], tmp_path / "plugins", store)

    await bot.setup_hook()

    assert bot.loaded == ("Alpha",)
    assert isinstance(bot.tree.translator, Translator)


@pytest.mark.usefixtures("installed")
@pytest.mark.parametrize(
    ("config", "logged"),
    [("plugins: 5\n", "config.yaml: plugins"), (None, "No bot token")],
)
async def test_config_failures(
    caplog: pytest.LogCaptureFixture, config: str | None, logged: str
) -> None:
    """Requirement: Startup loads the configured plugins."""
    if config is not None:
        write_config(config)

    assert await run(Options()) == 1
    assert logged in caplog.text
    assert Path("config.yaml").is_file()


@pytest.mark.usefixtures("installed")
@pytest.mark.parametrize(
    "error",
    [
        discord.LoginFailure("Improper token has been passed."),
        discord.PrivilegedIntentsRequired(None),
    ],
)
async def test_connection_refused(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error: discord.ClientException,
) -> None:
    """Requirement: Startup loads the configured plugins."""
    write_config("token: abc\n")
    closed = watch_closes(monkeypatch)

    async def start(_self: Bot, _token: str) -> None:
        raise error

    monkeypatch.setattr(Bot, "start", start)

    assert await run(Options()) == 1
    assert str(error) in caplog.text
    assert len(closed) == 1


async def never_connect(_self: Bot, _token: str) -> None:
    raise AssertionError


async def test_all_plugins_load(installed: FakePlugins, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Offline check."""
    installed.add("Alpha", PLUGIN, BUNDLE)
    write_config("plugins: [Alpha]\n")
    monkeypatch.setattr(Bot, "start", never_connect)

    assert await run(Options(no_online=True)) == 0
    assert Path("plugins/Alpha/config.yaml").is_file()
    assert Path("plugins/Alpha/lang/en-US/register.yaml").is_file()
    assert installed.calls() == ["setup", "teardown"]


@pytest.mark.parametrize("plugins", ["[Alpha, Ghost]", "[Alpha, Broken]"])
async def test_a_plugin_does_not_load(
    installed: FakePlugins, monkeypatch: pytest.MonkeyPatch, plugins: str
) -> None:
    """Requirement: Offline check."""
    installed.add("Alpha", PLUGIN, BUNDLE)
    installed.add("Broken", BROKEN)
    write_config(f"plugins: {plugins}\n")
    monkeypatch.setattr(Bot, "start", never_connect)

    assert await run(Options(no_online=True)) == 1


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
async def test_stop_signal(
    installed: FakePlugins, monkeypatch: pytest.MonkeyPatch, signum: signal.Signals
) -> None:
    """Requirement: Graceful stop."""
    installed.add("Alpha", PLUGIN, BUNDLE)
    write_config("token: abc\nplugins: [Alpha]\n")
    closed = watch_closes(monkeypatch)

    async def start(self: Bot, _token: str) -> None:
        await self.setup_hook()
        signal.raise_signal(signum)
        # Stands in for the gateway loop, which ends once the client is closed.
        while not self.is_closed():  # noqa: ASYNC110
            await asyncio.sleep(0.01)

    monkeypatch.setattr(Bot, "start", start)

    assert await run(Options()) == 0
    assert installed.calls() == ["setup", "teardown"]
    assert len(closed) == 1
