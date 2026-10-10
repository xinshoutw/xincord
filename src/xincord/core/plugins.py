"""Plugin discovery, ordering and the context each plugin gets.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:39-245
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:14-74
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/yaml/InfoSerializer.kt:7-40
"""

import importlib
import logging
import re
from dataclasses import dataclass, field, replace
from graphlib import CycleError, TopologicalSorter
from importlib import metadata
from importlib.resources import files
from typing import TYPE_CHECKING, TypeIs, cast

import discord

from xincord.core.config import load_config
from xincord.core.i18n import Lang, export_lang

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from importlib.metadata import EntryPoint
    from pathlib import Path

    from xincord.core.config import Model
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

    An extension's ``setup(bot)`` gets it with ``bot.plugin_context(__name__)``. It keeps what
    :meth:`config` and :meth:`lang` returned in ``reads``, which a :meth:`replaying` copy hands
    back instead of reading the files again.
    """

    info: PluginInfo
    directory: Path
    store: Store
    force_lang: bool = False
    reads: dict[str, object] = field(default_factory=dict[str, object], compare=False, repr=False)
    replay: bool = False

    @property
    def data_directory(self) -> Path:
        """The directory for the files that the plugin keeps itself."""
        raise NotImplementedError

    def config[M: Model](self, model: type[M]) -> M:
        """Load ``config.yaml`` as ``model``, created from the plugin's bundled default.

        Raises:
            ConfigError: The file is invalid.
            OSError: The plugin bundles no ``config.yaml``.
        """
        key = f"config:{model.__qualname__}"
        if self.replay and key in self.reads:
            return cast("M", self.reads[key])
        default = files(self.info.module).joinpath("config.yaml").read_text(encoding="utf-8")
        loaded = load_config(self.directory / "config.yaml", model, default)
        self.reads[key] = loaded
        return loaded

    def lang(self, default_locale: str) -> Lang:
        """Export the plugin's bundled ``lang`` directory where files are missing, then load it.

        Raises:
            LangError: The lang files are invalid.
        """
        key = f"lang:{default_locale}"
        if self.replay and key in self.reads:
            return cast("Lang", self.reads[key])
        target = self.directory / "lang"
        export_lang(files(self.info.module).joinpath("lang"), target, force=self.force_lang)
        loaded = Lang.load(self.info.name, target, default_locale)
        self.reads[key] = loaded
        return loaded

    def replaying(self) -> PluginContext:
        """Return a copy whose :meth:`config` and :meth:`lang` give back what they gave here.

        The core hands it to a plugin's previous version, which discord.py sets up again when a
        reload fails, so that the files that broke the new version cannot break it too.
        """
        return replace(self, replay=True)


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
