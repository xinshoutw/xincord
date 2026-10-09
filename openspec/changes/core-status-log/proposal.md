## Why

Two v3 runtime features remain: the rotating bot activity (`StatusChanger.kt`) and the
interaction log, which writes a console line for every interaction (`InteractionLogger.kt`) and
posts a formatted line to configured channels (`ConsoleLogger.kt`). The core config already
validates their settings (`status.activities`, `interaction_log`; Core change `core-config`).

## What Changes

- Status rotation: once the bot is ready it shows each configured activity for its `seconds`, in a
  loop; one activity is set once; a full reload restarts it with the new list.
- Console log line for each slash command, message command, button, select and modal:
  `[CMD] alice: /ticket create`, as v3 printed them.
- Log channels: each `interaction_log` target gets its `format` rendered with v3's user keys, the
  interaction keys, `cl_type` and `cl_interaction_string` for the interaction types it lists. The
  messages never ping; a full reload applies new targets.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/statuschanger/StatusChanger.kt:16-90`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-65`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/consolelogger/ConsoleLogger.kt:27-139`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:26-27`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:140-148`

Out of scope: the container (Core change `container`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-runtime`: status rotation and the interaction log.

## Impact

New modules `xincord.core.status` and `xincord.core.interaction_log`; `Bot` takes the core config,
runs the rotation and logs in `on_interaction`; `cli.run` passes the config. No new dependencies.
