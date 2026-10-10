## ADDED Requirements

### Requirement: Stored messages live in the plugin's own files
The plugin SHALL keep the stored messages in SQLite files under `data/ChatLogger/`, each named
`messages-<UTC time>.db` after the second from which it holds messages, up to the next file's; the
oldest also holds older ones. The first file SHALL start with the first stored message. Each
message SHALL be stored, changed, found and removed in the file whose range holds its ID. The
plugin SHALL drop the table that held them in `data/xincord.db`.

#### Scenario: First file
- **WHEN** the first message, created at 2026-10-11 12:00:05.250 UTC, is stored
- **THEN** `data/ChatLogger/` holds one file, `messages-20261011T120005Z.db`, which holds it

#### Scenario: No message, no file
- **WHEN** the plugin loads and no message was stored yet
- **THEN** no message file exists

#### Scenario: Messages of older files
- **WHEN** a message of an older file and a message of the newest file are edited, then deleted
- **THEN** both edits and both deletions are logged, and each message is changed and removed in its
  own file

#### Scenario: Late message
- **WHEN** a message created before the newest file's time arrives after that file started
- **THEN** it is stored in the older file whose range holds it, and its edit finds it there

#### Scenario: Files kept across loads
- **WHEN** the plugin loads again while message files exist
- **THEN** it finds the messages stored before and starts no file

#### Scenario: Old table
- **WHEN** `data/xincord.db` holds the `ChatLogger_messages` table of an earlier version
- **THEN** loading the plugin drops it without copying its rows

### Requirement: A new message file starts when the newest is full
After a message is stored in the newest file, the plugin SHALL check that file's size, and once it
holds `max_file_size_mb` or more, start a new file named after the second that follows the newest
stored message's creation, so that no stored message moves. A new file that cannot be created
SHALL be logged, the message SHALL stay stored, and the next message stored there SHALL try again.

#### Scenario: Full file
- **WHEN** a message created at 12:00:05.250 brings the newest file to the size limit
- **THEN** a new file `messages-<day>T120006Z.db` starts, the messages created from 12:00:06 on go to
  it, and the stored ones stay in the full file

#### Scenario: Size limit from the config
- **WHEN** `max_file_size_mb` is 1 and the stored messages fill 1 MiB
- **THEN** a second file starts

#### Scenario: New file fails
- **WHEN** the new file cannot be created
- **THEN** an error is logged, the message stays stored in the full file, and the next message
  stored there starts the new file

### Requirement: The message files are open while the plugin is loaded
The plugin SHALL open its message files when it loads, one connection per file on one thread of its
own, and close them when it unloads, after the store work under way. A reload SHALL close the files
before the new version opens them, and a load that fails SHALL leave none open. Store work that
comes once they are closed SHALL fail and leave the files unchanged.

#### Scenario: Unload
- **WHEN** the plugin unloads while a message is being stored
- **THEN** the message is stored and the files are closed

#### Scenario: Reload
- **WHEN** the plugin is reloaded
- **THEN** the previous version's files are closed, and the new version finds the messages stored
  before

#### Scenario: Failed load
- **WHEN** the plugin's checks fail while it loads into a ready bot
- **THEN** no message file stays open

#### Scenario: After closing
- **WHEN** a message comes once the files are closed
- **THEN** storing it fails and the files are unchanged

## MODIFIED Requirements

### Requirement: The config keeps v3's key and bounds the stored messages
`config.yaml` SHALL hold v3's `log_all`, true by default; `retention_days`, the days a message's text
is kept, 1826 (5 years) by default and from 1 to 3650; and `max_file_size_mb`, the size in MiB from
which a new message file starts, 256 by default and from 1 to 65536. v3's files SHALL load, their
`enabled` key only warning; any other value SHALL stop the plugin from loading, with the key named.

#### Scenario: v3's file
- **WHEN** `plugins/ChatLogger/config.yaml` is v3's, with `enabled: false` and `log_all: false`
- **THEN** the plugin loads with `log_all` false, 1826 days and 256 MiB, and a warning names
  `enabled`

#### Scenario: Invalid retention
- **WHEN** `retention_days` is 0, 3651 or a text
- **THEN** the plugin does not load and the error names `retention_days`

#### Scenario: Invalid file size
- **WHEN** `max_file_size_mb` is 0, 65537 or a text
- **THEN** the plugin does not load and the error names `max_file_size_mb`

### Requirement: Stored messages are kept for the retention period
When the bot is ready, and every hour after, the plugin SHALL delete the stored messages created
more than `retention_days` days ago, as their IDs tell, and delete each message file whose range
ends before then. A failure SHALL be logged and the next hour SHALL try again; unloading the plugin
SHALL stop this, and a load that fails SHALL not start it.

#### Scenario: Old messages
- **WHEN** with the default 1826 days, messages created 1827 and 1825 days ago are stored and the
  bot becomes ready
- **THEN** the first is deleted and the second stays

#### Scenario: Expired files
- **WHEN** with 1826 days, the files' ranges end 1830 days ago, 1800 days ago and never, and the bot
  becomes ready
- **THEN** the first file is deleted, the second keeps only its messages younger than 1826 days,
  and the third stays

#### Scenario: Every hour
- **WHEN** an hour passes after READY
- **THEN** the old messages are deleted again

#### Scenario: Failure
- **WHEN** a deletion fails
- **THEN** an error is logged and the next hour deletes again

#### Scenario: Unload
- **WHEN** the plugin unloads
- **THEN** the hourly deletion stops

#### Scenario: Failed load
- **WHEN** the plugin loads into a ready bot and its checks of the guilds fail
- **THEN** the plugin is not loaded and no hourly deletion runs
