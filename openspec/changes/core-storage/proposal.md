## Why

v3 keeps plugin data in JSON files (one per plugin or per guild) and in an embedded MongoDB. Its
JSON writes are not atomic and a file that fails to parse is silently replaced by the default.
Decision B8 replaces both with one SQLite database.

## What Changes

- An async key-value store over one SQLite file: JSON values grouped by namespace, with get, put,
  delete, listing, and an atomic read-modify-write.
- An escape hatch that runs a function with the database connection, so plugins can create and
  query their own tables in the same transaction model.
- Keyed asyncio locks for plugin flows that span several awaits.
- A corrupt database stops startup instead of being reset.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonFileManager.kt:21-134`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/mongodb/CacheCollectionManager.kt:18-43`

Out of scope: importing v3 data (deferred, decision B11), plugin-specific tables (each plugin's
change), and where the database file lives (Core change `runtime`).

## Capabilities

### New Capabilities

- `core-storage`: the SQLite-backed store that plugins use for persistent data.

### Modified Capabilities

None.

## Impact

New module `xincord.core.storage`. No new dependencies (stdlib `sqlite3`).
