"""Reloading the config and the plugins.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:60-93
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:112-159
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import watch_syncs, write_config
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from plugin_fakes import FakePlugins
    from xincord.core.storage import Store

RECORDING = """
from .. import calls

NAME = __name__.rsplit(".", 1)[1]


async def setup(bot):
    calls.append(("setup", NAME))


async def teardown(bot):
    calls.append(("teardown", NAME))
"""
NEEDS_BETA = 'DEPENDS = ("Beta",)\n' + RECORDING
NEEDS_ALPHA = 'DEPENDS = ("Alpha",)\n' + RECORDING
NEEDS_MEMBERS = "import discord\n\nINTENTS = discord.Intents(members=True)\n" + RECORDING
BROKEN = """
async def setup(bot):
    raise RuntimeError("boom")
"""
SLOW = """
import asyncio

from .. import calls


async def setup(bot):
    calls.append("start")
    await asyncio.sleep(0)
    calls.append("end")
"""


async def started(installed: FakePlugins, store: Store, enabled: list[str]) -> Bot:
    """A bot that loaded ``enabled``, with the same list in ``config.yaml``."""
    write_config(f"plugins: [{', '.join(enabled)}]\n")
    bot = installed.bot(enabled, Path("plugins"), store)
    assert await bot.load_plugins() == []
    installed.calls().clear()
    return bot


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Reload follows the config")
async def test_config_changed(installed: FakePlugins, store: Store) -> None:
    """Requirement: Reload follows the config."""
    for name in ("Alpha", "Beta", "Gamma"):
        installed.add(name, RECORDING)
    installed.add("Delta", NEEDS_BETA)
    bot = await started(installed, store, ["Alpha", "Beta", "Delta"])
    write_config("plugins: [Alpha, Delta, Gamma]\n")

    summary = await bot.reload()

    assert summary == "Reloaded: Alpha, Gamma. Failed: Delta (see the log)."
    assert bot.loaded == ("Alpha", "Gamma")
    assert installed.calls() == [
        ("teardown", "delta"),
        ("teardown", "beta"),
        ("teardown", "alpha"),
        ("setup", "alpha"),
        ("setup", "gamma"),
    ]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Reload follows the config")
async def test_failures(installed: FakePlugins, store: Store) -> None:
    """Requirement: Reload follows the config."""
    installed.add("Alpha", RECORDING)
    installed.add("Epsilon", NEEDS_MEMBERS)
    bot = await started(installed, store, ["Alpha"])
    installed.replace("Alpha", BROKEN)
    write_config("plugins: [Alpha, Epsilon]\n")

    summary = await bot.reload()

    assert summary == "Reloaded: none. Failed: Alpha, Epsilon (see the log)."
    assert bot.loaded == ("Alpha",)
    # discord.py runs the previous setup again after the new one failed.
    assert installed.calls() == [("teardown", "alpha"), ("setup", "alpha")]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Reload follows the config")
async def test_invalid_config(installed: FakePlugins, store: Store) -> None:
    """Requirement: Reload follows the config."""
    installed.add("Alpha", RECORDING)
    bot = await started(installed, store, ["Alpha"])
    write_config("plugins: 5\n")

    summary = await bot.reload()

    assert summary.startswith("Reload failed: config.yaml: plugins")
    assert bot.loaded == ("Alpha",)
    assert installed.calls() == []


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Reload one plugin with its dependents"
)
async def test_named_plugin(installed: FakePlugins, store: Store) -> None:
    """Requirement: Reload one plugin with its dependents."""
    installed.add("Alpha", RECORDING)
    installed.add("Beta", NEEDS_ALPHA)
    bot = await started(installed, store, ["Alpha", "Beta"])
    write_config("plugins: 5\n")  # not read for a single plugin

    assert await bot.reload("Alpha") == "Reloaded: Alpha, Beta."
    assert await bot.reload("Ghost") == "Reload failed: plugin Ghost is not loaded"
    assert installed.calls() == [
        ("teardown", "alpha"),
        ("setup", "alpha"),
        ("teardown", "beta"),
        ("setup", "beta"),
    ]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Reloads upload the commands")
@pytest.mark.parametrize(("ready", "uploads"), [(True, [("global", True), (1, True)]), (False, [])])
async def test_upload_after_reload(
    installed: FakePlugins,
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    ready: bool,  # noqa: FBT001
    uploads: list[tuple[str | int, bool]],
) -> None:
    """Requirement: Reloads upload the commands and never overlap."""
    bot = await started(installed, store, [])
    syncs = watch_syncs(bot, store, monkeypatch)

    def is_ready(_: Bot) -> bool:
        return ready

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "guilds", property(lambda _: [SimpleNamespace(id=1, name="One")]))

    assert await bot.reload() == "Reloaded: none."
    assert syncs == uploads


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="Reloads never overlap")
async def test_concurrent_reloads(installed: FakePlugins, store: Store) -> None:
    """Requirement: Reloads upload the commands and never overlap."""
    installed.add("Slow", SLOW)
    bot = await started(installed, store, ["Slow"])

    await asyncio.gather(bot.reload(), bot.reload())

    assert installed.calls() == ["start", "end", "start", "end"]
