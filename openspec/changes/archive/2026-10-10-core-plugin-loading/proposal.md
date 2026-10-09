## Why

v3 loads every plugin jar it finds, orders them with a hand-written dependency walk (then loads
them in reverse), aggregates intents from `info.yaml`, and lets each plugin check its own
`enabled` flag in every handler. Decisions B3 and B4 ask for discord.py extensions and Cogs found
through entry points, metadata as module constants, `graphlib` ordering, per-plugin isolation,
files under `plugins/<Name>/`, intents aggregated before connecting, and hot reload that follows
dependencies.

## What Changes

- Discovery through the entry-point group `xincord.plugins`, limited to the plugins the core
  config enables, with metadata read from module constants.
- Dependency ordering with `graphlib`; plugins with missing or cyclic dependencies are left out.
- Intents aggregated from the plugins that will load, before the bot is created.
- A bot class that loads the plugins in order, isolates failures, gives each plugin a context
  (directory, config, lang, store), reloads a plugin together with its dependents, and refuses to
  hot-load a plugin that needs intents the connection lacks.
- The core config gains the `plugins` list; the v3 migration fills it from the plugins whose v3
  config has `enabled: true`.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:39-245`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:14-74`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/yaml/InfoSerializer.kt:7-40`

Out of scope: the CLI, console and `/xincord reload` command that call these functions, logging
in and syncing commands (Core changes `command-tree` and `runtime`), member cache settings (added
when a plugin needs them), and each plugin's own config migration.

## Capabilities

### New Capabilities

- `core-plugins`: discovering, ordering, loading, isolating and reloading plugins.

### Modified Capabilities

- `core-config`: the core config lists the enabled plugins, and the v3 migration fills that list.

## Impact

New modules `xincord.core.plugins` and `xincord.core.bot`; `CoreConfig` gains `plugins`;
`migrate_v3` reads the v3 plugin configs. No new dependencies.
