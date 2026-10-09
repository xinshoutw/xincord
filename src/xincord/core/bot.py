"""The xincord bot: discord.py's ``commands.Bot`` plus plugin loading.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:145-180
"""

import logging
from typing import TYPE_CHECKING, cast

import discord
from discord.ext import commands

from xincord.core.command_tree import CommandTree
from xincord.core.plugins import PluginContext, PluginError, required_intents

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from pathlib import Path

    from xincord.core.component_ids import ComponentIds, ParsedId
    from xincord.core.plugins import PluginInfo
    from xincord.core.storage import Store

    type Handler = Callable[[discord.Interaction, ParsedId], Awaitable[None]]

logger = logging.getLogger(__name__)

ROUTED = (discord.InteractionType.component, discord.InteractionType.modal_submit)


class Bot(commands.Bot):
    """Loads plugins as discord.py extensions, isolating each one's failures."""

    def __init__(
        self,
        plugins: Sequence[PluginInfo],
        *,
        root: Path,
        store: Store,
        force_lang: bool = False,
    ) -> None:
        """Create a bot for ``plugins`` (from :func:`discover`) with the intents they need.

        Args:
            plugins: The plugins to load, dependencies first.
            root: The directory that holds ``<Name>/`` for each plugin.
            store: The store shared by all plugins.
            force_lang: Replace exported lang files with the bundled ones.
        """
        # Application commands only: the prefix just satisfies commands.Bot.
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=required_intents(plugins),
            help_command=None,
            tree_cls=CommandTree,
        )
        self._plugins = tuple(plugins)
        self._root = root
        self._store = store
        self._force_lang = force_lang
        self._contexts: dict[str, PluginContext] = {}
        self._loaded: dict[str, PluginInfo] = {}
        self._routes: dict[str, list[tuple[ComponentIds, Handler]]] = {}

    @property
    def loaded(self) -> tuple[str, ...]:
        """The names of the loaded plugins, in load order."""
        return tuple(self._loaded)

    def plugin_context(self, module: str) -> PluginContext:
        """Return the context of the plugin whose extension module is ``module``.

        Raises:
            PluginError: No plugin with that module is being loaded or loaded.
        """
        try:
            return self._contexts[module]
        except KeyError:
            msg = f"no plugin loads from {module}"
            raise PluginError(msg) from None

    def route(self, module: str, ids: ComponentIds, handler: Handler) -> None:
        """Send the component and modal interactions whose IDs ``ids`` owns to ``handler``.

        Call it from the setup of the plugin whose extension module is ``module``.

        Raises:
            PluginError: No plugin loads from ``module``.
        """
        name = self.plugin_context(module).info.name
        self._routes.setdefault(name, []).append((ids, handler))

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Route component and modal interactions to the plugin that owns their ID."""
        if interaction.type not in ROUTED:
            return
        custom_id = cast("Mapping[str, object]", interaction.data or {}).get("custom_id")
        if not isinstance(custom_id, str):
            return
        for plugin, routes in self._routes.items():
            for ids, handler in routes:
                if ids.owns(custom_id):
                    await self._handle(plugin, ids, handler, interaction, custom_id)
                    return

    async def _handle(
        self,
        plugin: str,
        ids: ComponentIds,
        handler: Handler,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        try:
            await handler(interaction, ids.parse(custom_id))
        except Exception:
            logger.exception("Plugin %s failed to handle %s", plugin, custom_id)

    async def load_plugins(self) -> list[str]:
        """Load the plugins in order and return the names of those that did not load."""
        failed: list[str] = []
        for info in self._plugins:
            if missing := [dep for dep in info.depends if dep not in self._loaded]:
                logger.error("Plugin %s is skipped: %s did not load", info.name, ", ".join(missing))
                failed.append(info.name)
                continue
            try:
                await self._load(info)
            except PluginError:
                logger.exception("Plugin %s is disabled", info.name)
                failed.append(info.name)
        return failed

    async def load_plugin(self, info: PluginInfo) -> None:
        """Load a plugin after startup, for example one enabled since.

        Raises:
            PluginError: The plugin is already loaded, needs intents the bot was created without
                or a dependency that is not loaded, or fails to load.
        """
        if info.name in self._loaded:
            msg = f"plugin {info.name} is already loaded"
            raise PluginError(msg)
        if missing := [flag for flag, on in info.intents if on and not getattr(self.intents, flag)]:
            msg = f"plugin {info.name} needs the {', '.join(missing)} intents; restart to load it"
            raise PluginError(msg)
        if absent := [dep for dep in info.depends if dep not in self._loaded]:
            msg = f"plugin {info.name} needs {', '.join(absent)}, which is not loaded"
            raise PluginError(msg)
        await self._load(info)

    async def reload_plugin(self, name: str) -> list[str]:
        """Reload plugin ``name``, then the loaded plugins that depend on it; return their names.

        Raises:
            PluginError: The plugin is not loaded, or a reload failed. The plugin that failed
                keeps its previous version and the ones after it are not reloaded.
        """
        if name not in self._loaded:
            msg = f"plugin {name} is not loaded"
            raise PluginError(msg)
        affected = {name}
        for info in self._loaded.values():
            if info.name != name and affected.isdisjoint((*info.depends, *info.soft_depends)):
                continue
            # Whichever setup runs next registers the routes again.
            self._routes.pop(info.name, None)
            try:
                # discord.py restores the previous module when the new one fails.
                await self.reload_extension(info.module)
            except commands.ExtensionError as error:
                msg = f"plugin {info.name} failed to reload: {error}"
                raise PluginError(msg) from error
            affected.add(info.name)
        return [info.name for info in self._loaded.values() if info.name in affected]

    async def _load(self, info: PluginInfo) -> None:
        context = PluginContext(info, self._root / info.name, self._store, self._force_lang)
        self._contexts[info.module] = context
        try:
            await self.load_extension(info.module)
        except commands.ExtensionError as error:
            del self._contexts[info.module]
            self._routes.pop(info.name, None)
            msg = f"plugin {info.name} failed to load: {error}"
            raise PluginError(msg) from error
        self._loaded[info.name] = info
