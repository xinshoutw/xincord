## MODIFIED Requirements

### Requirement: v3 plugin switches migrate to the enabled list
Migrating a v3 directory SHALL set `plugins` to the names of the directories under `plugins/`
whose v3 `config.yaml` has `enabled: true`, each renamed plugin under its new name (decision B18
as amended on 2026-10-10), sorted by name, and report them.

#### Scenario: Enabled v3 plugins
- **WHEN** a v3 directory has `plugins/AutoRole` with `enabled: true`, `plugins/Ticket` with
  `enabled: false` and `plugins/SQLiteAPI` without a config
- **THEN** the migrated config lists only AutoRole and the report names it

#### Scenario: Renamed plugins
- **WHEN** a v3 directory enables `_Example`, `BasicCalculator`, `SimpleCommand`,
  `WelcomeByeGuild`, `IntervalPusher`, `Feedbacker`, `TicketAddons`, `NtustManager` and
  `NtustCourse`
- **THEN** the migrated config lists `Calculator`, `CustomCommands`, `Example`, `Feedback`,
  `NtustAnnouncements`, `NtustCourseWatch`, `TicketAwayNotice`, `UptimeHeartbeat` and
  `WelcomeGoodbye`, and the report names them

## ADDED Requirements

### Requirement: Renamed plugins' v3 directories move to their new names
Migrating a v3 directory SHALL move each renamed plugin's directory, `plugins/<v3 name>/`, to
`plugins/<new name>/` with its files, so that the plugin finds v3's config and lang files there,
and report each move. When `plugins/<new name>/` exists already, both directories SHALL stay as
they are and the report SHALL say so. Nothing SHALL move when the core config is already in the
new schema or backed up.

#### Scenario: Directory moved
- **WHEN** a v3 directory with `plugins/Feedbacker/config.yaml` is migrated
- **THEN** that file is now `plugins/Feedback/config.yaml`, `plugins/Feedbacker` is gone and the
  report names both directories

#### Scenario: New directory exists
- **WHEN** a v3 directory with both `plugins/Feedbacker` and `plugins/Feedback` is migrated
- **THEN** both keep their files and the report says that `plugins/Feedback` exists

#### Scenario: Migrated directory is left alone
- **WHEN** the core config is already in the new schema, or its backup already exists
- **THEN** no plugin directory moves
