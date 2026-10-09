"""The xincord bot: discord.py's ``commands.Bot`` plus plugin loading.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:145-180
"""

import logging
from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.plugins import PluginContext, PluginError, required_intents

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from xincord.core.plugins import PluginInfo
    from xincord.core.storage import Store

logger = logging.getLogger(__name__)


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
        )
        self._plugins = tuple(plugins)
        self._root = root
        self._store = store
        self._force_lang = force_lang
        self._contexts: dict[str, PluginContext] = {}
        self._loaded: dict[str, PluginInfo] = {}

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

    async def _load(self, info: PluginInfo) -> None:
        context = PluginContext(info, self._root / info.name, self._store, self._force_lang)
        self._contexts[info.module] = context
        try:
            await self.load_extension(info.module)
        except commands.ExtensionError as error:
            del self._contexts[info.module]
            msg = f"plugin {info.name} failed to load: {error}"
            raise PluginError(msg) from error
        self._loaded[info.name] = info
