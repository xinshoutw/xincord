"""The xincord bot: discord.py's ``commands.Bot`` plus plugin loading.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:145-180
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:112-159
"""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, cast, override

import discord
from discord.ext import commands

from xincord.core.admin import Xincord
from xincord.core.command_tree import CommandTree
from xincord.core.component_ids import ComponentIdError, upgrade_view
from xincord.core.config import (
    CORE_CONFIG,
    ConfigError,
    CoreConfig,
    default_core_config,
    load_config,
)
from xincord.core.i18n import Translator
from xincord.core.interaction_log import log
from xincord.core.plugins import PluginContext, PluginError, discover, required_intents
from xincord.core.status import rotate

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from pathlib import Path

    from xincord.core.component_ids import ComponentIds, ParsedId
    from xincord.core.plugins import PluginInfo
    from xincord.core.storage import Store

    type Handler = Callable[[discord.Interaction, ParsedId], Awaitable[None]]

logger = logging.getLogger(__name__)

ROUTED = (discord.InteractionType.component, discord.InteractionType.modal_submit)
# B19: messages ping users only; a message passes its own allowed_mentions to opt in.
ALLOWED_MENTIONS = discord.AllowedMentions(
    everyone=False, users=True, roles=False, replied_user=True
)


class Bot(commands.Bot):
    """Loads plugins as discord.py extensions, isolating each one's failures."""

    def __init__(
        self,
        plugins: Sequence[PluginInfo],
        *,
        root: Path,
        store: Store,
        force_lang: bool = False,
        config: CoreConfig | None = None,
    ) -> None:
        """Create a bot for ``plugins`` (from :func:`discover`) with the intents they need.

        Args:
            plugins: The plugins to load, dependencies first.
            root: The directory that holds ``<Name>/`` for each plugin.
            store: The store shared by all plugins.
            force_lang: Replace exported lang files with the bundled ones.
            config: The core config, for the status rotation and the interaction log.
        """
        # Application commands only: the prefix just satisfies commands.Bot.
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=required_intents(plugins),
            help_command=None,
            tree_cls=CommandTree,
            allowed_mentions=ALLOWED_MENTIONS,
        )
        self._plugins = tuple(plugins)
        self._root = root
        self._store = store
        self._force_lang = force_lang
        self._contexts: dict[str, PluginContext] = {}
        # The previous version's context of each plugin being reloaded, replaying (see _reload).
        self._previous: dict[str, PluginContext] = {}
        self._loaded: dict[str, PluginInfo] = {}
        self._routes: dict[str, list[tuple[ComponentIds, Handler]]] = {}
        self._reloading = asyncio.Lock()
        self._config = config or CoreConfig()
        self._status: asyncio.Task[None] | None = None
        self._relayed: set[str] = set()

    @override
    async def setup_hook(self) -> None:
        """Set the command translator and load the plugins before the gateway connects."""
        await self.tree.set_translator(Translator())
        self.tree.add_command(Xincord(extras={"global": True}))
        await self.load_plugins()
        logger.info("Plugins loaded: %s", ", ".join(self.loaded) or "none")

    async def on_ready(self) -> None:
        """Upload the commands that changed: the global ones, then each guild's."""
        await self._sync_commands(force=False)
        for guild in self.guilds:
            logger.info("Guild loaded: %s (%s)", guild.name, guild.id)
        self._rotate_status(restart=False)  # on_ready fires again after reconnects
        logger.info("Bot ready")

    @override
    async def close(self) -> None:
        """Stop the status rotation, unload the plugins and disconnect."""
        if self._status is not None:
            self._status.cancel()
        await super().close()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Upload the guild commands to a guild the bot joined."""
        await cast("CommandTree", self.tree).sync_guild(self._store, guild.id, force=True)
        logger.info("Guild joined: %s (%s)", guild.name, guild.id)

    async def reload(self, plugin: str | None = None) -> str:
        """Reload ``plugin`` with its dependents, or the core config and every plugin.

        Returns:
            A one-line summary, also logged. Failures are logged and summarized, not raised.
        """
        async with self._reloading:
            try:
                if plugin is None:
                    config = load_config(CORE_CONFIG, CoreConfig, default_core_config())
                    reloaded, failed = await self._reload_all(config.plugins)
                    self._config = config
                else:
                    reloaded, failed = await self.reload_plugin(plugin), []
            except (ConfigError, PluginError) as error:
                logger.exception("Reload failed")
                return f"Reload failed: {error}"
            if self.is_ready():
                # A manual reload also repairs the commands on Discord.
                await self._sync_commands(force=True)
                if plugin is None:
                    self._rotate_status(restart=True)
        summary = f"Reloaded: {', '.join(reloaded) or 'none'}."
        if failed:
            summary += f" Failed: {', '.join(failed)} (see the log)."
        logger.info("%s", summary)
        return summary

    @property
    def loaded(self) -> tuple[str, ...]:
        """The names of the loaded plugins, in load order."""
        return tuple(self._loaded)

    def plugin_context(self, module: str) -> PluginContext:
        """Return the context of the plugin whose extension module is ``module``.

        While discord.py sets up a plugin's previous version again after a failed reload, the
        context replays what that version loaded (:meth:`PluginContext.replaying`).

        Raises:
            PluginError: No plugin with that module is being loaded or loaded.
        """
        try:
            context = self._contexts[module]
        except KeyError:
            msg = f"no plugin loads from {module}"
            raise PluginError(msg) from None
        # discord.py takes a failed reload's modules out of sys.modules before it sets up the
        # previous version, and puts that version's modules back after it; every load's setup runs
        # with its module in sys.modules.
        previous = self._previous.get(module)
        return previous if previous is not None and module not in sys.modules else context

    def relay_gateway_event(self, name: str) -> None:
        """Dispatch each gateway event ``name`` as ``gateway_<name in lower case>``.

        For events that discord.py does not parse, such as ``VOICE_CHANNEL_STATUS_UPDATE``:
        listeners (``on_gateway_voice_channel_status_update``) get Discord's payload as their only
        argument. discord.py's own parser of the event, if it has one, runs first. Relaying an
        event again changes nothing, and the relay lasts as long as the bot.

        Args:
            name: The gateway event, as Discord names it.
        """
        # The table of parsers that discord.py's gateway looks every event up in, shared by all
        # of the client's connections.
        parsers = self._connection.parsers
        if name in self._relayed:
            return
        self._relayed.add(name)
        event = f"gateway_{name.lower()}"
        parse = parsers.get(name)

        def relay(payload: dict[str, object]) -> None:
            if parse is not None:
                parse(payload)
            self.dispatch(event, payload)

        parsers[name] = relay

    def route(self, module: str, ids: ComponentIds, handler: Handler) -> None:
        """Send the component and modal interactions whose IDs ``ids`` owns to ``handler``.

        Call it from the setup of the plugin whose extension module is ``module``.

        Raises:
            PluginError: No plugin loads from ``module``.
        """
        name = self.plugin_context(module).info.name
        self._routes.setdefault(name, []).append((ids, handler))

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Route component and modal interactions to the plugin that owns their ID, then log."""
        if interaction.type in ROUTED:
            await self._route(interaction)
        # After routing, so posting to log channels never delays a plugin's response.
        await log(self, interaction, self._config.interaction_log)

    async def _route(self, interaction: discord.Interaction) -> None:
        custom_id = str(cast("Mapping[str, object]", interaction.data or {}).get("custom_id", ""))
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
            fields = ids.parse(custom_id)
            await handler(interaction, fields)
        except Exception:
            logger.exception("Plugin %s failed to handle %s", plugin, custom_id)
            return
        if fields.legacy:
            await self._upgrade(interaction)

    async def _upgrade(self, interaction: discord.Interaction) -> None:
        """Edit the interaction's message once so its legacy IDs use the new format."""
        message = interaction.message
        if message is None or message.flags.ephemeral:
            return
        codecs = [ids for routes in self._routes.values() for ids, _ in routes]
        try:
            # Fetch again: the handler may have edited the message already.
            current = await message.channel.fetch_message(message.id)
            view_type = discord.ui.LayoutView if current.flags.components_v2 else discord.ui.View
            view = view_type.from_message(current, timeout=None)
            if upgrade_view(view, codecs):
                view.stop()  # the router handles these items, not discord.py
                await current.edit(view=view)
        except discord.HTTPException, ComponentIdError:
            logger.exception("Upgrading the component IDs of message %s failed", message.id)

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
            await self._reload(info)
            affected.add(info.name)
        return [info.name for info in self._loaded.values() if info.name in affected]

    async def _reload_all(self, enabled: Sequence[str]) -> tuple[list[str], list[str]]:
        """Make the loaded plugins match ``enabled``; return the reloaded and the failed ones."""
        wanted = discover(enabled)
        names = {info.name for info in wanted}
        # Dependents load after their dependencies, so they unload first.
        for name in reversed(self.loaded):
            if name not in names:
                await self._unload(name)
        failed: list[str] = []
        for info in wanted:
            try:
                if info.name in self._loaded:
                    await self._reload(info)
                else:
                    await self.load_plugin(info)
            except PluginError:
                logger.exception("Plugin %s did not reload", info.name)
                failed.append(info.name)
        self._plugins = tuple(wanted)
        failed += [name for name in dict.fromkeys(enabled) if name not in names]
        return [name for name in self.loaded if name not in failed], failed

    async def _reload(self, info: PluginInfo) -> None:
        # Whichever setup runs next registers the routes again.
        self._routes.pop(info.name, None)
        previous = self._contexts[info.module]
        self._contexts[info.module] = PluginContext(
            info, self._root / info.name, self._store, self._force_lang
        )
        # When the new version fails, discord.py sets up the previous one again; it gets the config
        # and lang it loaded before, not the files that broke the new one.
        self._previous[info.module] = previous.replaying()
        try:
            await self.reload_extension(info.module)
        except Exception as error:
            if info.module in self.extensions:  # the previous version runs again
                self._contexts[info.module] = previous
                msg = f"plugin {info.name} failed to reload: {error}"
                raise PluginError(msg) from error
            await self._drop(info)
            msg = f"plugin {info.name} failed to reload and is unloaded: {error}"
            raise PluginError(msg) from error
        finally:
            del self._previous[info.module]

    async def _drop(self, info: PluginInfo) -> None:
        """Forget a plugin whose previous version failed to set up again after a failed reload.

        discord.py leaves what that setup added before it failed; it goes too.
        """
        await self._remove_module_references(info.module)
        del self._loaded[info.name]
        del self._contexts[info.module]
        self._routes.pop(info.name, None)

    async def _unload(self, name: str) -> None:
        info = self._loaded.pop(name)
        self._routes.pop(name, None)
        await self.unload_extension(info.module)
        del self._contexts[info.module]
        logger.info("Plugin %s unloaded", name)

    def _rotate_status(self, *, restart: bool) -> None:
        if self._status is not None and not self._status.done():
            if not restart:
                return
            self._status.cancel()
        self._status = asyncio.create_task(rotate(self, self._config.status.activities))

    async def _sync_commands(self, *, force: bool) -> None:
        tree = cast("CommandTree", self.tree)
        await tree.sync_global(self._store, force=force)
        for guild in self.guilds:
            await tree.sync_guild(self._store, guild.id, force=force)

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
