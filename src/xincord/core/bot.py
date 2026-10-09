"""The xincord bot: discord.py's ``commands.Bot`` plus plugin loading.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:145-180
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from xincord.core.plugins import PluginContext, PluginInfo
    from xincord.core.storage import Store


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
        raise NotImplementedError

    @property
    def loaded(self) -> tuple[str, ...]:
        """The names of the loaded plugins, in load order."""
        raise NotImplementedError

    def plugin_context(self, module: str) -> PluginContext:
        """Return the context of the plugin whose extension module is ``module``.

        Raises:
            PluginError: No plugin with that module is being loaded or loaded.
        """
        raise NotImplementedError

    async def load_plugins(self) -> list[str]:
        """Load the plugins in order and return the names of those that did not load."""
        raise NotImplementedError
