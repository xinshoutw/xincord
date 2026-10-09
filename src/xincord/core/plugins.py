"""Plugin discovery and ordering.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:39-245
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/yaml/InfoSerializer.kt:7-40
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from importlib.metadata import EntryPoint

GROUP = "xincord.plugins"


class PluginError(Exception):
    """A plugin cannot be discovered, loaded or reloaded; the message names it."""


@dataclass(frozen=True)
class PluginInfo:
    """What the core knows about a plugin before loading it."""

    name: str
    module: str
    depends: tuple[str, ...] = ()
    soft_depends: tuple[str, ...] = ()
    intents: discord.Intents = field(default_factory=discord.Intents.none)


def discover(
    enabled: Sequence[str], entry_points: Iterable[EntryPoint] | None = None
) -> list[PluginInfo]:
    """Return the enabled plugins that can load, each after its dependencies.

    Args:
        enabled: Plugin names from the core config.
        entry_points: The installed plugins; defaults to the ``xincord.plugins`` group.

    Plugins that are not installed, fail to import, declare invalid metadata, or miss a
    dependency are logged and left out.
    """
    raise NotImplementedError


def required_intents(plugins: Iterable[PluginInfo]) -> discord.Intents:
    """Return discord.py's default intents plus those of ``plugins``."""
    raise NotImplementedError
