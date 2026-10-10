## Context

`port-chat-logger` answered decision B8's open question (does ChatLogger's large message log get
its own file?) with no: the log is one plugin table, `ChatLogger_messages`, in the shared
`data/xincord.db`, reached through `Store.run` on the store's one worker thread, which every plugin
shares, and bounded by `retention_days` (30 by default) through an hourly deletion in batches
(`messages.MessageLog`, `cog.ChatLogger.prune`). Edits and deletions wait for the insert of their
message under way (`ChatLogger.inserting`), so an edit that arrives together with its message is
logged.

On 2026-10-10 the owner decided otherwise (`HANDOFF.md` section 6): messages are kept for 5 years
by default, and the log moves to its own SQLite files under the plugin's data directory inside the
`data/` volume, a new file starting automatically when the current one grows too large.

Volume: a stored message takes about 130 bytes with the index for a 60-character text (measured,
2026-10-11), about 200 bytes for 40 Chinese characters. A guild with 2,000 messages a day keeps
about 700 MB over five years; one with 20,000 a day about 7 GB. On the owner's Mac, one SQLite
transaction per message commits about 2,000 times a second.

## Goals / Non-Goals

**Goals:** the owner's decision, test-first; B8's rules for the new files (blocking SQLite work off
the event loop, one writer per file, every write awaited); the atomicity that `port-chat-logger`
built (each operation one transaction, an edit arriving with its message still logged); files
closed when the plugin unloads, no connection left behind by a reload or a failed load; a plan for
importing v3's message files.

**Non-Goals:** building `xincord migrate`; compacting (`VACUUM`), compressing or encrypting files;
purging or exporting the log on command; moving other plugins' data out of the store; changing
what is stored or logged.

## Decisions

### Core API: a data directory per plugin

`Store.run` (and the plugin's `transaction`) roll back when the commit itself fails, as when
another program holds a lock on the file past the 5-second wait (found in the cross-review): the
write transaction stayed open, and the next call's commit applied the failed call's writes.

`PluginContext.data_directory: Path` is `<data>/<Name>/`, where `<data>` is the bot's new
keyword-only argument `Bot(..., data=...)`. The program passes `data/` (`cli.DATA`), the directory
that already holds `xincord.db` and that the container keeps in the `data` volume; `DATABASE` is
now `DATA / "xincord.db"`. The core creates nothing, so a plugin that keeps no files there leaves
no directory. `data` has no default, so that
no caller writes into a working directory by accident; tests pass `tmp_path / "data"`, and
`plugin_fakes.load_plugin` passes the sibling of its plugins root. Plugin names match
`[A-Za-z0-9_-]+`, so `data/<Name>/` never meets `xincord.db` or its journal. This is the smallest
API for the owner's "under the plugin's data directory inside the `data/` volume"; the store
stays as it was.

### Files and their ranges

`data/ChatLogger/messages-<start>.db`, where `<start>` is a UTC second in ISO 8601's basic format
(`messages-20261011T120005Z.db`): readable, sorted by name, and parsed back into the file's first
snowflake (`discord.utils.time_snowflake(start)`). The names are the only record of the ranges:
file *i* holds the messages whose IDs lie from its start up to the next file's start; the oldest
file also holds the IDs below its own start (messages created a moment before the first one
arrived, or imported ones). `files.route(first_ids, message_id)` is a bisection. Other names in the
directory are ignored. No file exists until the first message is stored; the first file is named
after the second in which that message was created.

Each file holds one table, the columns of `port-chat-logger` (v3's plus the guild and the channel):

```sql
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    update_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_guild ON messages (guild_id);
```

Every operation names its file by the message's ID: `add` (`INSERT OR IGNORE`, so a replayed event
keeps the first row), `edit` (read, compare and update in one transaction), `pop` and `pop_all`
(one transaction per file, the results oldest first). `forget(guild_id)` and `guild_ids()` visit
every file (rare: a guild left with `log_all` false). Edits and deletions of a message in an older
file are found there at once, without searching.

### Starting a new file

After `add` stores a message in the newest file, the same transaction reads `PRAGMA page_count`,
which SQLite answers from its header in constant time; once `page_count * page_size` reaches
`max_file_size_mb` MiB, a new file starts. Its start is the second after the newest stored message
was created (`files.next_start`: the floor of `snowflake_time(max(message_id))` plus one second,
and at least the newest file's start plus one second), so every stored ID stays below it and no row
ever moves: routing gives each ID the same file before and after the split, nothing is lost or
stored twice. Messages created in the rest of that second still go to the full file; the size is a
threshold, not a cap. Only the newest file starts a successor; a late message stored in an older
file can take that file a little beyond the limit.

The new file is created as `messages-<start>.db.tmp`, given its table and closed, then renamed to
its name and opened: a name in the directory is always a complete file, and SQLite's journal, which
follows the path a connection opened, never meets a renamed file. A temporary file that a failed or
interrupted attempt left is removed when the files open and before its name is built again; a file
that cannot be opened after its rename is removed, so that a restart never reads a range away from
the messages that the full file takes meanwhile. When creating it fails (a full disk), the stored
message stays and the next message stored in the full file tries again; the first failure is logged
with its traceback, the later ones of the same episode at debug level, and the file that finally
starts at info level. An attempt costs about a millisecond, so there is no back-off.

The default, 256 MiB, keeps a file easy to copy or open in a database browser and leaves a small
guild in one file for years; it bounds the space that deleted rows leave in a file until the whole
file expires. The bounds, 1 to 65,536 MiB (64 GiB), refuse a size typed in bytes.

### One thread, one connection per file

`MessageFiles` owns a `ThreadPoolExecutor` with one worker (`xincord-chat-logger`), created by
`open` and shut down by `close`, and one `sqlite3` connection per file, created and used on that
thread only (default rollback journal and `synchronous`, as the core store). Each public method is
one job on that thread and awaited on the event loop; the list of files is touched only there, so
routing, a split and a file's deletion never interleave with another job. Each file has one
connection, its only writer. The log no longer waits for, or delays, the other plugins' store calls.

### Opening and closing

`ChatLogger.cog_load` opens the files (registering every `messages-*.db` in the directory, creating
the table where it is missing; a corrupt file fails the load and stays as it is), then runs the
READY checks of a ready bot (closing the files again if they fail), then starts the retention loop.
`cog_unload` cancels the loop and closes the files: `close` refuses new work at once and closes the
connections in a job queued after the work already submitted, so a message being stored when the
plugin unloads is stored. The job runs even when the caller is cancelled (a shutdown during a
reload), and a cancelled `open` queues the same job after its own, so that what it opened closes.
A file that is not a database stops the load with an error that names it. Work that comes later (a listener task of the unloaded version) raises
`RuntimeError` without touching the files, and discord.py logs it; the core loses events between an
unload and the next load anyway. discord.py calls `cog_unload` when a plugin unloads, when a reload
replaces it (before the new version's `cog_load`) and when setup fails after the cog was added; a
failing `cog_load` closes the files itself. The cog creates `MessageFiles` in `__init__` without
opening anything.

### Retention

`MessageFiles.prune(before)` first deletes each file whose range ends at or before `before` (the
next file's start), never the newest: it closes the connection, takes the file out of the list,
then deletes the file and a journal left beside it, with an info line per file; a file that cannot
be deleted is logged with its name and stays on disk for the next start, and the others are still
deleted. Then it deletes
the expired rows of every file in batches of 1,000, each its own job, so inserts go on between
them. The cog's loop is unchanged (READY, then hourly) and logs `sqlite3.Error` and `OSError` and
tries again the next hour. Deleted rows leave free pages that SQLite reuses for new rows in that
file; a full file shrinks to nothing only when it expires as a whole.

### The old table

`setup` runs `DROP TABLE IF EXISTS ChatLogger_messages` through `Store.run` (its index goes with
it): xincord has no deployed data, so its rows are not copied. It is one cheap statement at each
load.

### Config

`retention_days` keeps its name and range (1 to 3650) and defaults to 1826: five years of 365.25
days, rounded down. The new `max_file_size_mb` (1 to 65,536, default 256) is in MiB (1,048,576
bytes), as SQLite's page sizes are. Both are in the bundled `config.yaml` with comments. An
existing `plugins/ChatLogger/config.yaml` keeps the `retention_days: 30` that the earlier bundle
wrote; there is no deployment to update.

### Migration of v3's message files (`xincord migrate`)

v3 kept `plugins/ChatLogger/data/<guildId>.db`, one table per channel named by the channel's ID,
columns `message_id INT PRIMARY KEY, user_id INT, message TEXT, update_count INT` (inventory 8.1).
The planned import runs with the bot stopped, before ChatLogger ever ran on the volume:

1. It refuses (and the dry run reports) a `data/ChatLogger/` that holds message files: rows older
   than an existing file would all go to the oldest one, which then holds years of history, cannot
   expire as a whole for years and never shrinks (found in the cross-review). The operator moves
   such files aside, which before the cutover only hold a test guild's messages.
2. For each file whose stem is a guild ID, it copies the file with its journal to a scratch
   directory and opens the copy read-write: v3 never closed its connections, so a hot journal can
   sit beside a file, and SQLite cannot roll it back through a read-only connection. It reads
   every table whose name is a channel ID (quoted: the names are numbers), each with `ORDER BY
   message_id`; other files and tables get a line in the report.
3. It keeps the rows younger than the configured `retention_days`, by their IDs, and counts the
   others.
4. It merges the tables' sorted rows of every guild into one stream ordered by message ID
   (`heapq.merge`; v3's files were never pruned, so nothing is loaded whole) and appends them with
   `MessageFiles` as `add` does, each row `(message_id, guild_id from the file name, channel_id
   from the table, user_id, message, update_count)`, in transactions of a few thousand rows:
   files start at the size limit exactly as in live operation, the first named after the oldest
   kept message, and `INSERT OR IGNORE` makes a second run add nothing.
5. The dry run prints the rows to import and the rows expired per guild, and the number of files
   that all guilds' rows will fill together.

v3 kept the text of deleted messages (its deletion only read the row), so the import brings them
back, and they stay until the retention removes them; their deletion was handled by v3 and no
later event removes them. v3's text was taken from the content or the embeds with its defects
(inventory 12, item 14); the import copies it as it is, and later edits compare against it.

### Checks (2026-10-11)

- The built `xincord-plugins` wheel holds `files.py`, `messages.py`, `config.yaml` and the 16 lang
  files.
- `docker compose build` and `docker compose run --rm -T bot --no-online` with `plugins:
  [ChatLogger]`: the plugin loads, `plugins/ChatLogger/config.yaml` holds `retention_days: 1826`
  and `max_file_size_mb: 256`, and `data/` holds `xincord.db` only (no message, no file).
- A probe in the image (user `xincord`, uid 1000) stored 61 messages of 4,000 characters, created
  a second apart 1,830 days ago, through `MessageFiles` with a 64 KiB limit into
  `/bot/data/ChatLogger/` in the named volume: five files, the full ones 64 KiB each, mode 644; an
  edit found the first message; the retention at 1,826 days deleted the four full files and 8 rows
  of the newest, which kept a message stored now. The test volume was removed afterwards.

### Cross-review (a subagent, 2026-10-11)

A review of the pushed work, aimed at other paths into the features, retries and residual state,
found two problems of weight and five small ones; this change fixes them (tasks 8.1 to 8.7):

1. A commit that failed (another program holding a read lock past the 5-second wait, such as a
   database browser) left the write transaction open, and the next job's commit applied it: a
   deletion was applied without its log. The plugin's `transaction` and the core's `Store.run`,
   which had the same defect, roll back when the commit fails.
2. The import plan put v3's whole history into the oldest file when `data/ChatLogger/` already held
   files: the import refuses such a directory, opens copies of v3's files (a hot journal defeats a
   read-only open), merges sorted cursors instead of sorting in memory, and says that v3's rows of
   deleted messages come back until the retention ("Migration").
3. A cancelled `open` or `close` left connections open: the closing job is queued whatever happens
   to the caller.
4. A corrupt file stopped the load without its name: the error names the file.
5. A split that keeps failing logged a traceback at every message, which would rotate the other
   logs away under compose's 30 MB: one error per episode.
6. Temporary files left by a crash stayed until the same name came up: opening removes them. An
   expired file that could not be deleted stopped the deletion of the others: each is tried.
7. The failed load and the reload were tested without files on disk: they now have files and a
   collection that fails on a leaked connection; a setup that fails after the cog was added and
   `Bot.close` got tests; `decisions.md` records the owner's answer to B8 (Amendment 3).

The review also found sound: routing, splitting and expiry in a randomized model check (200 seeds
of 600 operations with late, out-of-order, old and replayed IDs, splits failing before and after
the rename, batch sizes of 1, 3 and 1,000, and restarts: no message lost, duplicated, misrouted or
unfindable, every row inside its file's range); `next_start` and the names over the whole 41-bit
time range; every load and unload path (a hot reload, a failed reload with the previous version
set up again, the core's `_drop`, `Bot.close`, `--no-online`, a failed load into a ready bot with
files on disk: never two connections to one file, nothing left open); `inserting`; and a
`--no-online` run beside a running bot, which neither changes the files nor waits.

### Tests

- `tests/plugins/chat_logger/test_files.py`: the names, `route`, `next_start` and `expired`.
- `test_message_files.py`: `MessageFiles` in a temporary directory, with a size limit of 1 byte
  (every message stored in the newest file starts the next one, which makes the ranges exact) or
  64 KiB with 4,000-character texts (about a page each): no file before the first message, the
  first file, routing, splits, late messages, reopening, other names, a corrupt file (named), a
  failing split (before and after the rename, twice in a row, leftover temporary files), a commit
  that fails on another connection's read lock (`BUSY_TIMEOUT` shortened), closing after the work
  under way, work after closing, a cancelled open and close (the connections are made by the test,
  closable from its thread, and checked one by one), whole files expiring, an expired file that
  cannot be deleted. Rows are read back through connections of the test's own.
- `test_storage.py`: the plugin's side (the first file through discord.py's parsers, the old table
  dropped, a split at `max_file_size_mb: 1` with edits and deletions in both files, unload,
  reload, failed load); `test_retention.py`: the 5-year default and expired files at READY.
- `conftest.py`: the `load` fixture removes the cog of every plugin a test loaded, closing its files
  (Python 3.13+ warns about connections collected unclosed, and pytest turns the warning into an
  error); the autouse `plugin_modules` fixture lets a test reload the plugin; `Scene.rows` reads the
  files; `write_file` writes a file as an earlier run left it. `plugin_fakes.unclosed()` collects
  the garbage and returns the warnings about unclosed connections, which a test asserts empty: left
  to the collector, such a warning fails a later test, after the call that xfail watches.
- The core: `test_plugins.py` (the context's directory) and `test_startup.py` (the program's
  `data/`).
- Found while reviewing the implementation, fixed test-first (tasks 6.3 and 6.4): a corrupt
  temporary file left by a failed attempt blocked its name, and a new file that failed after its
  rename stayed under its name, where a restart would have read its range away from the messages
  that the full file took meanwhile.

## v3 behaved differently

- v3 behaved differently: the message log was one SQLite file per guild under
  `plugins/ChatLogger/data/`, beside the config and the lang files, one table per channel, growing
  forever; it lives in files of time ranges under `data/ChatLogger/`, inside the data volume, split
  at a size and deleted as a whole once expired.
- v3 behaved differently: v3 created a guild's database file and a channel's table on the gateway
  thread at the first message and never closed the connections (inventory 12, item 7); the files
  open and close with the plugin, on a thread of their own.

## User-visible changes

1. Messages are kept for 5 years by default: `retention_days: 1826` in the bundled `config.yaml`
   (was 30), with its comment.
2. New config key `max_file_size_mb` (256 by default, 1 to 65,536) with a comment.
3. The log moves from `data/xincord.db` to `data/ChatLogger/messages-<UTC time>.db` (still in the
   `data` volume); the first file appears with the first stored message, a new one when the newest
   reaches the size, and a file whose messages all expired is deleted. Backups must copy
   `data/ChatLogger/` too; a file is best copied while the bot is stopped.
4. Log lines: `ChatLogger started the message file ...` and `ChatLogger deleted the message file
   ..., whose messages all expired` (info); errors when a new file cannot be created (once per
   episode) and when an expired file cannot be deleted; a corrupt file's error names it.
5. The `ChatLogger_messages` table of earlier xincord builds is dropped from `data/xincord.db` at
   load; messages stored there are not kept.
6. Every plugin: a store write whose commit fails (another program holding a lock on
   `data/xincord.db` for more than 5 seconds) is rolled back and raises, instead of being committed
   later by another write.

## Risks / Trade-offs

- Five years of message content are kept by default, in files that anyone with the volume can
  read; the privacy notes of `port-chat-logger` weigh more (a left guild's messages with `log_all`
  true now stay up to five years; the owner's open choice in the review queue).
- The files are copied safely only when the bot is stopped (or with SQLite's backup API); a copy
  taken during a write can miss that transaction.
- Store work that comes after an unload fails (a listener task of the unloaded version, a moment
  long); discord.py logs it.
- A commit that waits more than 5 seconds for another program's lock on a file (a database browser
  holding a read transaction open) fails and is rolled back: that message's storing, edit or
  deletion is lost, with an error in the log. Inspect copies of the files, or close the browser's
  transaction.
- Space that deleted rows (deletions, `forget`, the retention) leave inside a file is reused only by
  that file, which is deleted only when its range expires: at most about one file's worth.
- The size check runs after messages stored in the newest file only, and rows stored in an older
  file (late or imported) can take it beyond the limit.

## Manual smoke checklist

With a bot token, `plugins: [ChatLogger]` and the setup of `port-chat-logger`'s checklist (a test
guild, a listen channel detecting `#general`, two accounts); on the host or under compose (`docker
compose exec bot ls -l data/ChatLogger`):

1. Start with an empty `data/` (or an empty volume): `data/xincord.db` exists, `data/ChatLogger/`
   does not. Send a message in `#general`: `data/ChatLogger/messages-<UTC second>.db` appears.
2. Edit the message, then delete it: both are logged as before.
3. Set `max_file_size_mb: 1` and reload (`/xincord reload ChatLogger`); post until the file passes
   1 MiB (about 500 messages of 2,000 characters, from a script through a webhook): the log says
   that a new file started, and `data/ChatLogger/` holds two files. Edit and delete a message sent
   before the split and one sent after it: all four are logged.
4. Stop the bot, start it again: no new file starts, and editing a message stored before the
   restart is logged.
5. A day after step 3, set `retention_days: 1` and reload: the full file is deleted with an info
   line, the newest stays, and edits of messages older than a day are no longer logged.
6. `sqlite3 data/xincord.db ".tables"` shows no `ChatLogger_messages`.

## Inventory audit

`docs/porting/analysis/inventory/ChatLogger.md`, against this change (the rest stays as
`port-chat-logger` audited it):

- Persistence (8.1): v3's per-guild files and per-channel tables become files of time ranges with
  one table ("Stored messages live in the plugin's own files"); v3's columns stay, with the guild
  and the channel, so the import can copy v3's rows ("Migration"); retention, which v3 lacked, is
  "Stored messages are kept for the retention period", now with whole files ("Expired files"); the
  size limit is "A new message file starts when the newest is full"; v3's start-up maintenance with
  `log_all` false stays "Data is forgotten with the guild".
- Migration and compatibility (8): v3's files are read by `xincord migrate` ("Migration"), not by
  the plugin.
- External dependencies (9): SQLiteAPI's connections by key become `MessageFiles`' connections, one
  per file, on the plugin's thread.
- Concurrency (11): JDA's single gateway thread became discord.py's tasks; each operation is one job
  on the plugin's thread, and the inserts under way still order a message's edits and deletions
  ("Edited at once", "Deleted at once", unchanged).
- Bugs (12): item 7 (connections never closed) is "The message files are open while the plugin is
  loaded"; item 17 (stray file names breaking start-up) holds for the new files too: names that are
  not `messages-<UTC time>.db` are ignored.
