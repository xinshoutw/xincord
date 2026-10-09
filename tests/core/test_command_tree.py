"""The command tree.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-41
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:18-36
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import discord
import pytest
from discord import app_commands

from xincord.core.bot import Bot
from xincord.core.command_tree import CommandTree
from xincord.core.storage import Store

if TYPE_CHECKING:
    from pathlib import Path


@app_commands.command(name="ping", description="Ping")
async def ping(interaction: discord.Interaction) -> None:
    """Do nothing."""


@app_commands.command(name="form", description="Open a form", extras={"defer": False})
async def form(interaction: discord.Interaction) -> None:
    """Do nothing."""


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
