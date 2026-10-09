## Context

v3's console `reload` called `BotLoader.reload()`: stop JDA, unload every plugin, close the class
loaders, then start again, reconnecting to the gateway. The Web Dashboard reloaded one plugin and
re-uploaded the commands (`BotLoader.kt:125-159`); it is not ported (B13). xincord already has
`Bot.reload_plugin` (with dependents, keeping the previous version on failure) and `load_plugin`
(refusing new intents).

## Goals / Non-Goals

**Goals:** one reload entry point for SIGHUP, `/xincord reload` and the coming console; the
plugin set follows the config; the gateway stays connected.

**Non-Goals:** the console (`core-console`); re-applying the status rotation and interaction log
(`core-status-log` hooks into the same reload); reloading the token or the store.

## Decisions

- **Entry point.** `Bot.reload(plugin=None) -> str` returns a one-line summary and logs it.
  Config and plugin errors are logged with their traceback and summarized as
  `Reload failed: <error>`; nothing is raised to the caller, so every trigger can show or log the
  result.
- **Full reload.** Re-read `config.yaml` (`CORE_CONFIG`, relative to the working directory like
  the CLI), `discover` its plugins, unload in reverse load order the loaded plugins that
  `discover` no longer returns (so dependents of a removed plugin go too), then for each wanted
  plugin in order: `reload_extension` if loaded, else `load_plugin`. A plugin that fails is
  logged and named in the summary, and the others continue. Listed plugins that are not loaded
  afterwards (not installed, missing dependency) count as failed too. The owner chose to unload
  removed plugins, as v3's restart did.
- **Single reload.** `reload_plugin(name)`: the plugin and the loaded plugins that depend on it;
  the core config is not read.
- **Uploads.** After a reload the bot uploads the global and every guild's commands with
  `force=True` if `is_ready()`: a manual reload is also the way to repair commands on Discord.
  Before the bot is ready, `on_ready` uploads them anyway.
- **No overlap.** An `asyncio.Lock` per bot serializes reloads; a SIGHUP during a slash-command
  reload waits.
- **Command.** `xincord.core.admin.Xincord`, an `app_commands.Group` subclass named `xincord`,
  `guild_only` and `default_permissions=Permissions()` (only administrators see it unless a server
  changes the integration settings), added as a global command in `setup_hook`. `reload` checks
  `bot.is_owner(user)`: the application owner, or the team's admins and developers. The tree has
  already deferred ephemerally, so replies go through `interaction.followup`. The `plugin` option
  autocompletes loaded plugin names by case-insensitive substring, at most 25.
- **SIGHUP.** `cli` adds a SIGHUP handler next to SIGINT and SIGTERM; it starts `bot.reload()` as a
  task that is kept referenced until done.

### v3 behaved differently

- v3 behaved differently: the console's `reload` disconnected from the gateway and rebuilt
  everything, so a plugin that failed after the reload stayed off; xincord stays connected and a
  plugin whose new version fails keeps its previous one.
- v3 behaved differently: nothing could reload from Discord or from a signal; single-plugin reloads
  needed the Web Dashboard.

## Risks / Trade-offs

- A reloaded module re-executes its imports; objects other plugins kept from the old module stay
  old until those plugins reload. Reloading by name reloads the dependents for that reason.
- Plugin code that keeps state outside its cog (module globals, tasks) must clean up in
  `teardown` or `cog_unload`; the port-plugin checklist already asks for it.

## User-visible changes

Approved by the owner on 2026-10-10 (English copy; removed plugins are unloaded):

1. New global, guild-only command `/xincord reload [plugin]` ("Manage the bot" / "Reload the
   config and the plugins, or one plugin" / "Plugin to reload with the plugins that depend on
   it"), visible to administrators by default and runnable by the owner only.
2. Ephemeral replies: `Reloaded: AutoRole, Ticket.`, `Reloaded: AutoRole. Failed: Economy (see the
   log).`, `Reload failed: <reason>`, `Only the bot owner can use this command.`
3. SIGHUP (`docker compose kill -s HUP bot`) reloads like the command without a plugin.
4. A reload keeps the gateway connected; plugins removed from the list are unloaded with their
   dependents.
