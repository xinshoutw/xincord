## Why

On 2026-10-10 the owner decided two things about ChatLogger's message log (`HANDOFF.md` section 6),
which replace the answer that `port-chat-logger` gave to decision B8 and its 30-day default:

1. Messages are kept for **5 years** by default (today: `retention_days`, 30 by default).
2. The log no longer lives in the shared `data/xincord.db` (today: the table `ChatLogger_messages`,
   reached through `Store.run`). It gets its own SQLite files under the plugin's data directory
   inside the `data/` volume, and a new file starts automatically when the current one grows too
   large.

Five years of a busy guild's messages would make one table, in the database that every plugin
shares on one thread, grow to gigabytes; its own files keep that volume and its writes away from
the other plugins, and a file whose messages have all expired is deleted as a whole.

## What Changes

- **Core:** each plugin's context names a data directory, `data/<Name>/`, next to the store's
  database inside the `data/` volume (`PluginContext.data_directory`; `Bot(..., data=...)`, which
  the program sets to `data/`). The core never creates it.
- ChatLogger keeps the stored messages in SQLite files under `data/ChatLogger/`, named
  `messages-<UTC time>.db` after the second from which each holds messages, up to the next file's
  second; the oldest file also holds older ones. The first file starts with the first stored
  message. A message is stored, edited, found and removed in the one file whose range holds its
  ID, so edits and deletions find messages in older files.
- After a message is stored in the newest file, the file's page count is checked; once the file
  holds `max_file_size_mb` (new config key, 256 by default), a new file starts after the newest
  stored message. Stored messages never move, so the split loses and duplicates nothing.
- `retention_days` defaults to 1826 (5 years). When the bot is ready and every hour, the retention
  deletes the expired messages and, as a whole, each file whose range ended before the retention.
- The files are open while the plugin is loaded: one thread of the plugin's own, one connection
  per file, every write awaited; they close when the plugin unloads, after the work under way, and
  a reload or a failed load leaves no connection behind. The insert that edits and deletions wait
  for (an edit arriving with its message) stays as it is.
- The plugin drops the `ChatLogger_messages` table of `data/xincord.db` without copying its rows
  (xincord has no deployed data).
- `design.md` describes how the planned `xincord migrate` imports v3's
  `plugins/ChatLogger/data/<guildId>.db` files into the new layout.
- **Core fix (found in the cross-review):** `Store.run` rolls back when its commit fails (another
  process holding a lock past the wait), as the plugin's files do; before, the next call's commit
  applied the failed call's writes.

v3's message store, which this change replaces a second time:
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:22-67`
  (the per-guild files at start-up)
- `XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:164-187`
  (`plugins/ChatLogger/data/<guildId>.db`, one table per channel)
- `XsDiscordBotKt@3a59607:Plugins/API/SQLiteAPI/src/main/kotlin/api/sqlite/SQLiteFileManager.kt:8-46`
  (the connections by key)

Out of scope: building `xincord migrate` (only its ChatLogger part is planned here); compacting
files (`VACUUM`), compressing or encrypting them; a command or config key to purge or export the
log; moving any other plugin's data out of the store; what is stored and logged, which stays as
`port-chat-logger` specified it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-chat-logger`: the config's retention default and the new size key, the retention of whole
  files (two modified requirements); the message files, the new file when one is full, and their
  lifecycle (three new ones).
- `core-plugins`: a data directory for each plugin (one new requirement).
- `core-storage`: a failed commit rolls back (one modified requirement).

## Impact

`src/xincord/core/plugins.py`, `bot.py` and `cli.py` (the data directory; every `Bot(...)` call
names it); `packages/xincord-plugins/src/xincord/plugins/chat_logger/` (`messages.py` rewritten
around the files, a new `files.py` for their names and ranges, `cog.py`, `config.py`, `__init__.py`
and the bundled `config.yaml`); their tests. No new dependency. Operators find the log in
`data/ChatLogger/` inside the `data` volume (its backup now covers that directory too), and the
plugin's files take up to five years of messages by default.
