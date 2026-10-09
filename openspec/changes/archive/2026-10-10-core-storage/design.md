## Context

v3 has three storage paths: `JsonFileManager` (one JSON file, Moshi), `JsonGuildFileManager` (one
JSON file per guild) and an embedded MongoDB with `{_id, value, timestamp}` documents
(`CacheCollectionManager.kt:31-38`). Decision B8 chooses SQLite through the standard library:
a key-value document table plus per-plugin tables where queries need them, every write awaited,
and per-guild locks.

## Goals / Non-Goals

**Goals:** one small async API covering what the v3 managers did; atomic, durable writes; no
silent data loss.

**Non-Goals:** an ORM, schema migrations for plugin tables, multiple database files, importing v3
data.

## Decisions

- **API** (`xincord.core.storage.Store`): `open(path)`, `close()`, `get`, `put`, `delete`,
  `keys`, `items`, `update(namespace, key, fn)`, `run(fn)` and `lock(key)`. Values are JSON
  (`None`, bool, int, float, str, lists, string-keyed dicts), encoded with `allow_nan=False`.
- **One connection, one thread.** All database work runs on a single worker thread
  (`ThreadPoolExecutor(max_workers=1)`) instead of `asyncio.to_thread`: a sqlite3 connection must
  not be used from several threads at once, and one thread serializes every operation without
  extra locking. Throughput is not a concern at this bot's scale.
- **Transactions.** The connection uses `autocommit=False`. `run(fn)` commits after `fn`
  returns and rolls back if it raises; every key-value method is built on `run`, so each call is
  one transaction. `update` reads, applies `fn` and writes inside one `run`, which makes it
  atomic; `fn` must be a pure, quick function because it runs on the database thread.
- **Table:** `kv(namespace TEXT, key TEXT, value TEXT, PRIMARY KEY (namespace, key)) WITHOUT
  ROWID`. Plugins name their own tables `<plugin>_<name>` and create them with `run`.
- **Locks:** `lock(key)` returns an `asyncio.Lock` from a dict keyed by string. Locks are never
  evicted; that is fine for the number of guilds this bot serves.
- **Opening** creates parent directories, then runs `PRAGMA quick_check` through the table setup,
  so a corrupt file raises `sqlite3.DatabaseError` before anything is written.

### v3 behaved differently

- v3 behaved differently: `JsonFileManager` replaced a file that failed to parse with the default
  and saved it immediately (`JsonFileManager.kt:29-67`), losing the data. A corrupt database now
  stops startup and is left untouched.
- v3 behaved differently: JSON files were written in place with `writeText`
  (`JsonFileManager.kt:100-113`), so a crash mid-write could truncate them, and IO errors on save
  were only logged. SQLite commits are atomic and a failed write raises.

## Risks / Trade-offs

- A slow plugin query blocks other database work. Accepted; queries are small. Plugins with heavy
  data (ChatLogger) may get their own file when ported (B8 note).

## User-visible changes

None.
