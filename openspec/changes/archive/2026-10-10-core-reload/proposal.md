## Why

The owner changes config files and plugin code while the bot runs and needs to apply them without
a restart. In v3 the console's `reload` stopped and restarted the whole runtime
(`JLineManager.kt:68-70`, `BotLoader.kt:112-123`) and the Web Dashboard reloaded single plugins
(`BotLoader.kt:125-159`). Decision B15 replaces both with SIGHUP and an owner-only
`/xincord reload [plugin]`; the console (Core change `core-console`) will call the same reload.

## What Changes

- `Bot.reload(plugin=None)` returns a one-line summary. Without a plugin it re-reads the core
  config, unloads the plugins that are no longer listed (and those whose dependencies left),
  reloads the loaded ones and loads the newly listed ones; with a plugin it reloads that plugin and
  its dependents. A failed reload keeps the previous version. The commands are then uploaded with
  force. Reloads never overlap.
- `/xincord reload [plugin]`: a global, guild-only command that only administrators see by
  default and only the application owner can run; it replies ephemerally with the summary and
  suggests the loaded plugin names.
- SIGHUP runs a full reload and logs the summary.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:60-93`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:112-159`

Out of scope: the interactive console and its `stop` command (Core change `core-console`);
restarting the status rotation and the interaction log on reload (Core change
`core-status-log`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-runtime`: reloading the config and the plugins, the owner's reload command and SIGHUP.

## Impact

`Bot` gains `reload`; new module `xincord.core.admin` with the `/xincord` command group; the
core config path moves to `xincord.core.config.CORE_CONFIG`; `xincord.core.cli` handles SIGHUP.
No new dependencies.
