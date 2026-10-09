## Why

v3 defers every slash and message-context command ephemerally in a global listener, uploads every
plugin's guild commands to every guild at each start and guild join, and registers global commands
separately. Decision B5 keeps the ephemeral defer with an opt-out through `extras`, keeps the
guild/global split, and asks to upload commands only when their payload changes.

## What Changes

- A command tree that defers application commands ephemerally before they run, unless a command
  opts out with `extras={"defer": False}`.
- Commands are guild commands unless `extras={"global": True}`; their payloads are translated with
  the tree's translator.
- Uploading a scope (global, or one guild) only when the hash of its payload changed since the
  last successful upload, or when forced; failures are logged and retried next time.
- The bot uses this tree.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-41`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:18-36`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:172-180`

Out of scope: calling the sync at startup, on guild join and after reloads, and setting the
translator (Core change `runtime`); routing component and modal interactions (Core change
`core-component-routing`).

## Capabilities

### New Capabilities

- `core-command-tree`: deferring application commands, splitting command scopes and syncing only
  what changed.

### Modified Capabilities

None.

## Impact

New module `xincord.core.command_tree`; `xincord.core.bot.Bot` uses its `CommandTree`.
