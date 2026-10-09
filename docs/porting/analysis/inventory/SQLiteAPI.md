# SQLiteAPI — porting inventory (branch `main`)

All paths are relative to `Plugins/API/SQLiteAPI/src/main/kotlin/api/sqlite/` unless prefixed.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/API/SQLiteAPI` (Gradle `:Plugins:API:SQLiteAPI`, `build.gradle.kts`, convention `xs-plugin-shadow` → shaded jar `SQLiteAPI-3.4.0-SNAPSHOT.jar`). There is no shared `Plugins/API/build.gradle.kts`. |
| Kotlin files / LOC | 2 files / 56 physical lines: Event 10, SQLiteFileManager 46 |
| Package | `tw.xinshou.discord.plugin.api.sqlite` |
| Entry | `object Event : PluginEvent(false)` (Event.kt:5) |
| Listener flag | `false` |

**Purpose:** a library-carrier plugin.
- It ships the SQLite JDBC driver (and unused Exposed ORM jars).
- It provides `SQLiteFileManager`, a process-global registry of named JDBC connections to SQLite files, shared by dependent plugins.

**info.yaml** (expanded):
- `author: xinshoutw`, `name: SQLiteAPI`, `coreApi: "3.4"`, `version: "3.4.0-SNAPSHOT"`.
- `main: "tw.xinshou.discord.plugin.api.sqlite.Event"`.
- Defaults: `component_prefix` = `sqliteapi@` (9 chars, so no warning).
- No intents, cache flags, member-cache policies or dependencies.

---

## 2. Lifecycle

**load()** (Event.kt:6-9) overrides the default **without** calling `super.load()`, which is harmless because there is no `lang/`. It:
1. Calls `Class.forName("org.sqlite.JDBC")`, which registers the driver with `DriverManager`.
2. Logs `SQLiteAPI loaded.`.

**unload() / reload()** are Core defaults (log only). **Open connections are never closed by SQLiteAPI.**

**Load order caveat** (Core):
- `PluginLoader.run()` calls `load()` in **reverse** dependency order: dependents first (PluginLoader.kt:106-111 builds a dependency-first order, and line 147 iterates it `reversed()`).
- So consumers' `load()` runs **before** `Class.forName("org.sqlite.JDBC")`.
- This works today only because ChatLogger opens connections lazily, on the first message event after all plugins are loaded.

There are no background jobs.

**State:** `SQLiteFileManager.dbConn: HashMap<String, PathConnection(filePath, connection)>` (SQLiteFileManager.kt:9, 42-45). It is process-global for the life of the plugin class loader.

---

## 3. Slash commands & context menus

None.

## 4. Components

None.

## 5. Events

None.

## 6. Configuration

None (no `config.yaml`).

## 7. Localization & templates

None.

---

## 8. Persistence

The plugin owns no schema. Consumers choose the file paths and tables.

The known consumer data, ChatLogger, is out of scope here but relevant for migration:
- One DB file per guild at `plugins/ChatLogger/data/<guildId>.db`.
- One table per channel named `'<channelId>'`, with columns `message_id INT PRIMARY KEY NOT NULL ON CONFLICT FAIL, user_id INT NOT NULL, message TEXT NOT NULL, update_count INT NOT NULL` (Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:168-187).

These files are plain SQLite, so Python's `sqlite3` reads them directly.

---

## 9. External dependencies

**Gradle** (`build.gradle.kts:5-10`, `api(...)`, shaded):

| Artifact | Version | Note |
|---|---|---|
| `org.xerial:sqlite-jdbc` | 3.51.1.0 | |
| `org.jetbrains.exposed:exposed-core` | 1.0.0 | **unused anywhere in the repo** (verified by grep) |
| `org.jetbrains.exposed:exposed-dao` | 1.0.0 | unused |
| `org.jetbrains.exposed:exposed-jdbc` | 1.0.0 | unused |

**API surface exposed to other plugins** (SQLiteFileManager.kt:8-46):
```kotlin
object SQLiteFileManager {
    fun getConnection(uniqueKey: String): java.sql.Connection?            // NOT synchronized; null if absent
    @Synchronized fun connect(uniqueKey: String, file: File): Connection    // opens "jdbc:sqlite:<file.canonicalPath>" (creates the file if missing);
                                                                            // throws javax.management.openmbean.KeyAlreadyExistsException if key exists
    @Synchronized fun disconnect(uniqueKey: String)                         // close + remove; throws NoSuchElementException if absent
    @Synchronized fun deleteDatabase(uniqueKey: String)                     // if key present: disconnect, then File(path).delete() (result ignored);
                                                                            // if absent: silent no-op
}
```

**Consumers** (grep of `Plugins/`):

| Consumer | Declares | Code usage |
|---|---|---|
| **ChatLogger** | `depend_plugins: [SQLiteAPI]` (Plugins/ChatLogger/src/main/resources/info.yaml:11-12) + `compileOnly(project(":Plugins:API:SQLiteAPI"))` | `DbManager` (listed below) |
| **DynamicVoiceChannel** | `depend_plugins: [SQLiteAPI]` (Plugins/DynamicVoiceChannel/src/main/resources/info.yaml:10-11) | **None.** The build file has no SQLiteAPI dependency and the code has no SQLite usage. It is a stale hard dependency. |

ChatLogger's `DbManager` uses:
- `getConnection("CL:<guildId>") ?: connect("CL:<guildId>", plugins/ChatLogger/data/<guildId>.db)` (DbManager.kt:164-166).
- `disconnect("CL:<channelId>")` (134-141).
- `deleteDatabase("<guildId>")` (125-127).

**Consumer-side contract bugs** (ChatLogger, for the cross-plugin spec):
- `disconnect()` iterates **channel IDs** (`JsonManager.dataMap` keys are channel IDs, JsonManager.kt:27,54), but connections are keyed by **guild ID**. It never matches; the `NoSuchElementException` is swallowed, so **connections are never closed**.
- `deleteDatabase(guildId)` omits the `"CL:"` prefix, so it is a silent no-op. Leaving a guild does not delete its DB file.

---

## 10. Discord requirements

None.

---

## 11. Concurrency

- Mutations are `@Synchronized` on the object monitor. `deleteDatabase` calls `disconnect` while holding the lock, which is fine because the lock is reentrant.
- `getConnection` reads the `HashMap` **without** synchronization: a data race with concurrent `connect`/`disconnect` (theoretical).
- The consumer pattern `getConnection(k) ?: connect(k, f)` is check-then-act. Two threads can both see `null`, and the second then gets `KeyAlreadyExistsException`. JDA dispatches events on one thread by default, so the practical risk is low.
- Connection objects are shared and used by consumers without locking.
- After a Core full reload, class loaders are closed and recreated (PluginLoader.kt:287-298). Unclosed connections from the old instance leak.

---

## 12. Bugs, quirks, dead code, hard-coded values

- Connections are not closed on unload (Event.kt has no `unload()` override). Combined with ChatLogger's key mismatch, nothing ever closes them.
- `connect` throws an unusual exception type, `javax.management.openmbean.KeyAlreadyExistsException` (SQLiteFileManager.kt:16).
- `deleteDatabase` ignores both the `File.delete()` result and missing keys.
- `getConnection` is unsynchronized.
- The Exposed dependencies are dead weight.
- DynamicVoiceChannel declares a dependency it does not use.
- **Behavior to preserve, if the API is kept:** the `connect`/`getConnection`/`disconnect`/`deleteDatabase` semantics above, including which calls raise and which are silent.

---

## 13. Testability

Fully unit-testable with temporary files, using `sqlite3`:
- connect creates the file and registers the key;
- a duplicate key raises;
- `get` on a missing key returns `None`;
- `disconnect` on a missing key raises;
- `delete` on a present key closes the connection and removes the file;
- `delete` on a missing key does nothing;
- paths are canonicalized, so two relative paths to the same file give the same DB.

No Discord doubles are needed.

---

## 14. Porting assessment

**Difficulty: Low.** Consider not porting it as a "plugin" at all.

**Suggested mapping:**
- A small shared module (`xsbot.api.sqlite`) with a `ConnectionRegistry` class: dict keyed by name, guarded by an `asyncio.Lock` or `threading.Lock`, raising `KeyError`/`FileExistsError`-style exceptions.
- Or let each Cog own an `aiosqlite` connection opened in `cog_load` and closed in `cog_unload`.
- If kept as a plugin dependency: load it **before** its dependents (fixing Core's reverse order) and close all connections on unload.

**Risks:**
- Blocking `sqlite3` calls on the event loop: use `aiosqlite` or `asyncio.to_thread`.
- Existing ChatLogger DB files must stay readable; the schema is above.
