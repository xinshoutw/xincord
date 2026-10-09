"""Plugin discovery, ordering and the context each plugin gets.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:39-245
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:14-74
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/yaml/InfoSerializer.kt:7-40
"""

import importlib
import logging
import re
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from importlib import metadata
from typing import TYPE_CHECKING, TypeIs, cast

import discord

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from importlib.metadata import EntryPoint
    from pathlib import Path

    from xincord.core.config import Model
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store

logger = logging.getLogger(__name__)

GROUP = "xincord.plugins"
NAME = re.compile(r"[A-Za-z0-9_-]+")  # also the directory under plugins/


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


@dataclass(frozen=True)
class PluginContext:
    """What the core gives one plugin: its directory, its files and the shared store.

    An extension's ``setup(bot)`` gets it with ``bot.plugin_context(__name__)``.
    """

    info: PluginInfo
    directory: Path
    store: Store
    force_lang: bool = False

    def config[M: Model](self, model: type[M]) -> M:
        """Load ``config.yaml`` as ``model``, created from the plugin's bundled default.

        Raises:
            ConfigError: The file is missing from the bundle or invalid.
        """
        raise NotImplementedError

    def lang(self, default_locale: str) -> Lang:
        """Export the plugin's bundled ``lang`` directory where files are missing, then load it.

        Raises:
            LangError: The lang files are invalid.
        """
        raise NotImplementedError


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
    installed = metadata.entry_points(group=GROUP) if entry_points is None else entry_points
    available = {entry.name: entry for entry in installed}
    infos: dict[str, PluginInfo] = {}
    for name in dict.fromkeys(enabled):
        if (entry := available.get(name)) is None:
            logger.error("Plugin %s is not installed", name)
            continue
        try:
            infos[name] = _read(entry)
        except Exception:
            logger.exception("Plugin %s cannot be used", name)
    return _order(infos)


def required_intents(plugins: Iterable[PluginInfo]) -> discord.Intents:
    """Return discord.py's default intents plus those of ``plugins``."""
    intents = discord.Intents.default()
    for plugin in plugins:
        intents |= plugin.intents
    return intents


def _read(entry: EntryPoint) -> PluginInfo:
    if not NAME.fullmatch(entry.name):
        msg = f"plugin name {entry.name!r} must match {NAME.pattern}"
        raise PluginError(msg)
    module = importlib.import_module(entry.module)
    depends = getattr(module, "DEPENDS", ())
    soft_depends = getattr(module, "SOFT_DEPENDS", ())
    intents = getattr(module, "INTENTS", discord.Intents.none())
    if not (_names(depends) and _names(soft_depends) and isinstance(intents, discord.Intents)):
        msg = (
            f"{entry.name}: DEPENDS and SOFT_DEPENDS must be tuples of plugin names "
            "and INTENTS a discord.Intents"
        )
        raise PluginError(msg)
    return PluginInfo(entry.name, entry.module, depends, soft_depends, intents)


def _names(value: object) -> TypeIs[tuple[str, ...]]:
    return isinstance(value, tuple) and all(
        isinstance(item, str) for item in cast("tuple[object, ...]", value)
    )


def _order(found: dict[str, PluginInfo]) -> list[PluginInfo]:
    """Drop plugins with missing dependencies or cycles, then sort dependencies first."""
    infos = dict(found)
    while True:
        missing = {
            name: [dep for dep in info.depends if dep not in infos] for name, info in infos.items()
        }
        if missing := {name: deps for name, deps in missing.items() if deps}:
            for name, deps in missing.items():
                logger.error("Plugin %s is left out: it needs %s", name, ", ".join(deps))
                del infos[name]
            continue
        graph = {
            name: [*info.depends, *(dep for dep in info.soft_depends if dep in infos)]
            for name, info in infos.items()
        }
        try:
            return [infos[name] for name in TopologicalSorter(graph).static_order()]
        except CycleError as error:
            cycle = sorted(set(error.args[1]))
        logger.error("Plugins %s are left out: they depend on each other", ", ".join(cycle))
        for name in cycle:
            del infos[name]
