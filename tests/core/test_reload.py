"""Reloading the config and the plugins."""

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import watch_syncs, write_config
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from plugin_fakes import FakePlugins
    from xincord.core.command_tree import CommandTree
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


NEEDS_DATA = """
from discord import app_commands
from discord.ext import commands

from .. import calls


class Probe(commands.Cog):
    pass


async def probe(interaction):
    pass


async def setup(bot):
    await bot.add_cog(Probe())
    bot.tree.add_command(app_commands.Command(name="probe", description="Probe", callback=probe))
    (bot.plugin_context(__name__).directory / "data.txt").read_text(encoding="utf-8")
    calls.append(("setup", "alpha"))
"""


def alpha_data() -> Path:
    """Write ``plugins/Alpha/data.txt``, which ``NEEDS_DATA`` reads; return it."""
    data = Path("plugins") / "Alpha" / "data.txt"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text("data", encoding="utf-8")
    return data


async def started(installed: FakePlugins, store: Store, enabled: list[str]) -> Bot:
    """A bot that loaded ``enabled``, with the same list in ``config.yaml``."""
    write_config(f"plugins: [{', '.join(enabled)}]\n")
    bot = installed.bot(enabled, Path("plugins"), store)
    assert await bot.load_plugins() == []
    installed.calls().clear()
    return bot


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


async def test_invalid_config(installed: FakePlugins, store: Store) -> None:
    """Requirement: Reload follows the config."""
    installed.add("Alpha", RECORDING)
    bot = await started(installed, store, ["Alpha"])
    write_config("plugins: 5\n")

    summary = await bot.reload()

    assert summary.startswith("Reload failed: config.yaml: plugins")
    assert bot.loaded == ("Alpha",)
    assert installed.calls() == []


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


@pytest.mark.parametrize(
    ("ready", "uploads"),
    [
        (True, [("global", False), (1, False)]),
        (False, []),
    ],
)
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


async def test_concurrent_reloads(installed: FakePlugins, store: Store) -> None:
    """Requirement: Reloads upload the commands and never overlap."""
    installed.add("Slow", SLOW)
    bot = await started(installed, store, ["Slow"])

    await asyncio.gather(bot.reload(), bot.reload())

    assert installed.calls() == ["start", "end", "start", "end"]


async def test_full_reload_after_a_drop(installed: FakePlugins, store: Store) -> None:
    """Requirement: Hot reload follows dependencies and intents."""
    installed.add("Alpha", NEEDS_DATA)
    installed.add("Beta", NEEDS_ALPHA)
    data = alpha_data()
    bot = await started(installed, store, ["Alpha", "Beta"])
    data.unlink()

    failed = await bot.reload("Alpha")
    data.write_text("data", encoding="utf-8")
    again = await bot.reload()

    assert failed.startswith(
        "Reload failed: plugin Alpha failed to reload and is unloaded, with Beta, until a full "
        "reload: "
    )
    assert again == "Reloaded: Alpha, Beta."
    assert bot.loaded == ("Alpha", "Beta")


async def test_upload_after_a_reload_that_unloads(
    installed: FakePlugins, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Reloads upload the commands and never overlap."""
    installed.add("Alpha", NEEDS_DATA)
    data = alpha_data()
    bot = await started(installed, store, ["Alpha"])
    syncs = watch_syncs(bot, store, monkeypatch)

    def is_ready(_: Bot) -> bool:
        return True

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "guilds", property(lambda _: [SimpleNamespace(id=1, name="One")]))
    data.unlink()

    summary = await bot.reload("Alpha")

    assert summary.startswith("Reload failed: ")
    assert bot.tree.get_command("probe") is None
    assert syncs == [("global", False), (1, False)]


async def test_summary_before_the_upload(
    installed: FakePlugins,
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Reloads upload the commands and never overlap."""
    bot = await started(installed, store, [])
    uploads: list[tuple[bool, bool]] = []

    async def sync_global(used: Store, *, force: bool = False) -> bool:
        assert used is store
        uploads.append(("Reloaded: none." in caplog.messages, force))
        return True

    def is_ready(_: Bot) -> bool:
        return True

    monkeypatch.setattr(cast("CommandTree", bot.tree), "sync_global", sync_global)
    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "guilds", property(lambda _: []))
    caplog.set_level(logging.INFO, logger="xincord.core.bot")

    assert await bot.reload() == "Reloaded: none."
    assert uploads == [(True, False)]


async def test_waiting_reload(
    installed: FakePlugins, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Reloads upload the commands and never overlap."""
    installed.add("Slow", SLOW)
    bot = await started(installed, store, ["Slow"])
    caplog.set_level(logging.INFO, logger="xincord.core.bot")

    await asyncio.gather(bot.reload(), bot.reload())

    assert caplog.messages.count("Waiting for the running reload to finish") == 1
