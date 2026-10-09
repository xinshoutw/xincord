"""The owner's reload command and SIGHUP.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:60-93
"""

import signal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import until, write_config
from xincord.core.admin import NOT_OWNER, Xincord
from xincord.core.bot import Bot
from xincord.core.cli import Options, run

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    import discord
    from discord import app_commands

    from plugin_fakes import FakePlugins
    from xincord.core.command_tree import CommandTree
    from xincord.core.storage import Store

    # discord.py types decorated group methods as unbound callbacks; tests call them directly.
    type Reload = Callable[[Xincord, discord.Interaction, str | None], Awaitable[None]]
    type Suggest = Callable[[discord.Interaction, str], Awaitable[list[app_commands.Choice[str]]]]

OWNER = 42
RECORD = """
from .. import calls


async def setup(bot):
    calls.append(bot.plugin_context(__name__).info.name)
"""


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bool]] = []

    async def send(self, content: str, *, ephemeral: bool) -> None:
        self.sent.append((content, ephemeral))


def interaction(bot: Bot, user_id: int) -> tuple[discord.Interaction, FakeFollowup]:
    followup = FakeFollowup()
    fake = SimpleNamespace(client=bot, user=SimpleNamespace(id=user_id), followup=followup)
    return cast("discord.Interaction", fake), followup


async def test_command_payload(store: Store, tmp_path: Path) -> None:
    """Requirement: Owner-only reload command."""
    bot = Bot([], root=tmp_path, store=store)
    await bot.setup_hook()

    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()

    (xincord,) = [payload for payload in global_payload if payload["name"] == "xincord"]
    (reload,) = xincord["options"]
    assert reload["name"] == "reload"
    assert reload["options"][0]["autocomplete"] is True
    assert xincord["dm_permission"] is False
    assert xincord["default_member_permissions"] == 0
    assert all(payload["name"] != "xincord" for payload in guild_payload)


@pytest.mark.parametrize(("user_id", "reply"), [(OWNER, "Reloaded: Alpha."), (7, NOT_OWNER)])
async def test_owner_and_others(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, user_id: int, reply: str
) -> None:
    """Requirement: Owner-only reload command."""
    bot = Bot([], root=tmp_path, store=store)
    bot.owner_id = OWNER
    reloads: list[str | None] = []

    async def reload(_self: Bot, plugin: str | None = None) -> str:
        reloads.append(plugin)
        return "Reloaded: Alpha."

    monkeypatch.setattr(Bot, "reload", reload)
    fake, followup = interaction(bot, user_id)
    group = Xincord()

    await cast("Reload", group.reload.callback)(group, fake, "Alpha")

    assert followup.sent == [(reply, True)]
    assert reloads == (["Alpha"] if user_id == OWNER else [])


async def test_plugin_suggestions(fake_plugins: FakePlugins, store: Store, tmp_path: Path) -> None:
    """Requirement: Owner-only reload command."""
    fake_plugins.add("Alpha", RECORD)
    fake_plugins.add("Beta", RECORD)
    bot = fake_plugins.bot(["Alpha", "Beta"], tmp_path / "plugins", store)
    assert await bot.load_plugins() == []
    fake, _ = interaction(bot, OWNER)

    choices = await cast("Suggest", Xincord().plugin_names)(fake, "AL")

    assert [(choice.name, choice.value) for choice in choices] == [("Alpha", "Alpha")]


async def test_hang_up_signal(installed: FakePlugins, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: SIGHUP reloads."""
    installed.add("Alpha", RECORD)
    installed.add("Gamma", RECORD)
    write_config("token: abc\nplugins: [Alpha]\n")

    async def start(self: Bot, _token: str) -> None:
        await self.setup_hook()
        write_config("token: abc\nplugins: [Alpha, Gamma]\n")
        # Without a handler, SIGHUP would end the test run.
        assert signal.getsignal(signal.SIGHUP) is not signal.SIG_DFL
        signal.raise_signal(signal.SIGHUP)
        await until(lambda: "Gamma" in self.loaded)
        signal.raise_signal(signal.SIGTERM)
        await until(self.is_closed)

    monkeypatch.setattr(Bot, "start", start)

    assert await run(Options()) == 0
    assert installed.calls() == ["Alpha", "Alpha", "Gamma"]
