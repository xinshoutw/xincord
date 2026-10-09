## Why

Every later Core change and every plugin reads YAML configuration. Decision B6 replaces the v3
config with a new schema validated by pydantic v2, warns on unknown keys instead of failing, and
keeps a migration path from the v3 files.

## What Changes

- A generic loader for YAML config files: typed validation, readable errors with the location of
  each problem, warnings for unknown keys, and the default file written when the file is missing.
- The new core config schema: bot token, rotating bot activities, and interaction log targets.
- A migration from the v3 core `config.yaml` to the new schema, keeping a backup of the original.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/SettingsLoader.kt:21-57`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/setting/SettingSerializer.kt`
- `XsDiscordBotKt@3a59607:Core/src/main/resources/config.yaml`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/statuschanger/StatusChanger.kt:51-90`
  (the activity string format only)
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/consolelogger/ConsoleLogger.kt:27-72`
  (the target settings only)

Out of scope: running the activity rotation and the interaction log (Core change `runtime`), the
`--token` override (`runtime`), plugin config schemas and their v3 migrations (each plugin's
change), and data migration (deferred, decision B11).

## Capabilities

### New Capabilities

- `core-config`: loading and validating configuration files, the core config schema, and the
  migration of the v3 core config.

### Modified Capabilities

None.

## Impact

New module `xincord.core.config`, new module `xincord.core.migrate_v3`, a default
`config.yaml` resource, and the runtime dependencies pydantic and PyYAML.
