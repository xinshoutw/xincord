"""The command tree.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-41
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:18-36
"""

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest
from discord import app_commands

from xincord.core.bot import Bot
from xincord.core.command_tree import CommandTree
from xincord.core.i18n import Lang, Translator
from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from aiohttp import ClientResponse


type AnyCommand = app_commands.Command[Any, ..., Any]


def command(name: str | app_commands.locale_str, **extras: object) -> AnyCommand:
    async def callback(interaction: discord.Interaction) -> None:
        """Do nothing."""

    return app_commands.Command(
        name=name, description=f"The {name} command", callback=callback, extras=extras
    )


ping = command("ping")
form = command("form", defer=False)
info = command("info", **{"global": True})
about = command("about", **{"global": True})
stats = command("stats")


async def report(interaction: discord.Interaction, message: discord.Message) -> None:
    """Do nothing."""


DEFAULT: list[object] = [ping, app_commands.ContextMenu(name="Report", callback=report)]
OPTED_OUT: list[tuple[discord.InteractionType, object]] = [
    (discord.InteractionType.application_command, form),
    (discord.InteractionType.autocomplete, ping),
    (discord.InteractionType.application_command, None),
]


@dataclass
class FakeResponse:
    deferred: list[tuple[bool, bool]] = field(default_factory=list[tuple[bool, bool]])

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.deferred.append((ephemeral, thinking))


@dataclass
class FakeInteraction:
    type: discord.InteractionType
    command: object
    response: FakeResponse = field(default_factory=FakeResponse)


async def check(interaction: FakeInteraction) -> bool:
    tree = CommandTree(discord.Client(intents=discord.Intents.none()))
    return await tree.interaction_check(cast("discord.Interaction", interaction))


@pytest.mark.parametrize("command", DEFAULT)
async def test_default_command(command: object) -> None:
    """Requirement: Application commands are deferred ephemerally."""
    interaction = FakeInteraction(discord.InteractionType.application_command, command)

    assert await check(interaction)

    assert interaction.response.deferred == [(True, True)]


@pytest.mark.parametrize(("kind", "command"), OPTED_OUT)
async def test_opt_out_and_autocomplete(kind: discord.InteractionType, command: object) -> None:
    """Requirement: Application commands are deferred ephemerally."""
    interaction = FakeInteraction(kind, command)

    assert await check(interaction)

    assert interaction.response.deferred == []


async def test_bot_uses_the_tree(tmp_path: Path) -> None:
    """Requirement: Application commands are deferred ephemerally."""
    store = await Store.open(":memory:")
    try:
        assert isinstance(Bot([], root=tmp_path, store=store).tree, CommandTree)
    finally:
        await store.close()


SYNCED = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Commands are uploaded only when they change"
)
SCOPED = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Commands are split into guild and global scopes",
)


@dataclass
class FakeHttp:
    """Records command uploads; uploads to ``failing`` guilds raise."""

    uploads: list[tuple[str | int, list[str]]] = field(
        default_factory=list[tuple[str | int, list[str]]]
    )
    failing: set[int] = field(default_factory=set[int])

    async def bulk_upsert_global_commands(
        self, _application_id: int, payload: list[dict[str, Any]]
    ) -> None:
        self.uploads.append(("global", [command["name"] for command in payload]))

    async def bulk_upsert_guild_commands(
        self, _application_id: int, guild_id: int, payload: list[dict[str, Any]]
    ) -> None:
        if guild_id in self.failing:
            response = cast("ClientResponse", SimpleNamespace(status=500, reason="boom"))
            raise discord.HTTPException(response, "boom")
        self.uploads.append((guild_id, [command["name"] for command in payload]))


@pytest.fixture
async def store() -> AsyncGenerator[Store]:
    opened = await Store.open(":memory:")
    yield opened
    await opened.close()


def tree_with(
    monkeypatch: pytest.MonkeyPatch, *commands: AnyCommand
) -> tuple[CommandTree, FakeHttp]:
    client = discord.Client(intents=discord.Intents.none(), application_id=1)
    http = FakeHttp()
    monkeypatch.setattr(client, "http", http)
    tree = CommandTree(client)
    add(tree, *commands)
    return tree, http


def add(tree: CommandTree, *commands: AnyCommand) -> None:
    for each in commands:
        tree.add_command(each)


@SCOPED
async def test_scopes_and_translation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Commands are split into guild and global scopes."""
    for locale, name in (("en-US", "ping"), ("zh-TW", "pong-tw")):
        (tmp_path / locale).mkdir()
        (tmp_path / locale / "register.yaml").write_text(
            f"ping:\n  name: {name}\n  description: Ping\n", encoding="utf-8"
        )
    lang = Lang.load("Example", tmp_path, "en-US")

    localized = command(lang.command("ping", "ping.name"))

    tree, _ = tree_with(monkeypatch, localized, info)
    await tree.set_translator(Translator())

    global_payload, guild_payload = await tree.payloads()

    assert [command["name"] for command in global_payload] == ["info"]
    assert [command["name"] for command in guild_payload] == ["ping"]
    assert guild_payload[0]["name_localizations"]["zh-TW"] == "pong-tw"


async def sync_all(tree: CommandTree, store: Store) -> list[bool]:
    return [
        await tree.sync_global(store),
        await tree.sync_guild(store, 1),
        await tree.sync_guild(store, 2),
    ]


@SYNCED
async def test_unchanged_commands_are_not_uploaded(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Commands are uploaded only when they change."""
    tree, http = tree_with(monkeypatch, ping, info)

    first = await sync_all(tree, store)
    second = await sync_all(tree, store)

    assert first == [True, True, True]
    assert second == [False, False, False]
    assert http.uploads == [("global", ["info"]), (1, ["ping"]), (2, ["ping"])]


@SYNCED
async def test_changes_forcing_and_failures(
    store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Commands are uploaded only when they change."""
    tree, http = tree_with(monkeypatch, ping, info)
    await sync_all(tree, store)
    http.uploads.clear()
    add(tree, about, stats)
    http.failing = {2}

    with caplog.at_level(logging.ERROR):
        changed = await sync_all(tree, store)
    http.failing = set()
    retried = await tree.sync_guild(store, 2)
    unchanged = await tree.sync_guild(store, 1)
    forced = await tree.sync_guild(store, 1, force=True)

    assert changed == [True, True, False]
    assert "2" in caplog.text
    assert (retried, unchanged, forced) == (True, False, True)
    assert http.uploads == [
        ("global", ["info", "about"]),
        (1, ["ping", "stats"]),
        (2, ["ping", "stats"]),
        (1, ["ping", "stats"]),
    ]
