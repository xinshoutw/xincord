# core-command-tree Specification

## Purpose
Gives every application command an ephemeral "thinking" response unless it opts out, keeps guild
and global commands apart, and uploads commands to Discord only when they change.

## Requirements

### Requirement: Application commands are deferred ephemerally
Before a slash or context menu command runs, the bot's command tree SHALL defer the response
ephemerally with a thinking indicator, unless the command's `extras` sets `defer` to false.
Autocomplete interactions SHALL NOT be deferred.

#### Scenario: Default command
- **WHEN** a slash command or a context menu command without `extras` is invoked
- **THEN** its response is deferred ephemerally with a thinking indicator before it runs

#### Scenario: Opt-out and autocomplete
- **WHEN** a command with `extras={"defer": False}` is invoked, or an option is autocompleted
- **THEN** nothing is deferred

### Requirement: Commands are split into guild and global scopes
Commands SHALL be guild commands, registered in each guild the bot is in, unless their `extras`
sets `global` to true. A guild command whose `extras` sets `guilds` to a collection of guild IDs
SHALL be registered in those guilds only. Payloads SHALL be built with the tree's translator when
it has one.

#### Scenario: Scopes and translation
- **WHEN** the tree has a `ping` command localized in zh-TW and an `info` command marked global
- **THEN** the guild payload holds `ping` with its zh-TW name and the global payload holds only
  `info`

#### Scenario: Guild list
- **WHEN** the tree has `ping` and a `shop` command whose `extras` lists guild 1, and the commands
  are synced to guilds 1 and 2
- **THEN** guild 1 receives `ping` and `shop`, and guild 2 receives only `ping`

### Requirement: Commands are uploaded only when they change
The tree SHALL upload a scope's commands (global, or one guild's) only when the SHA-256 of its
payload differs from the hash stored after that scope's last successful upload, or when forced. A
failed upload SHALL be logged and SHALL leave the stored hash unchanged.

#### Scenario: Unchanged commands are not uploaded
- **WHEN** commands are synced to two guilds twice without changes
- **THEN** the first sync uploads the global scope and both guilds and the second uploads nothing

#### Scenario: Changes, forcing and failures
- **WHEN** a global command changes, one guild is forced, and another guild's upload fails
- **THEN** the global scope and the forced guild are uploaded, the failure is logged, and the
  failed guild is uploaded again on the next sync
