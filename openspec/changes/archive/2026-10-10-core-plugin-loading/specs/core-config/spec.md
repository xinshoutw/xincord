# Spec Delta

## ADDED Requirements

### Requirement: The core config lists the enabled plugins
The core config SHALL have `plugins`, the names of the plugins to load in the order given (default
none). The shipped default SHALL enable none.

#### Scenario: Plugins list
- **WHEN** the default core config loads, and a config lists AutoRole and Ticket
- **THEN** the default enables no plugin and the other keeps both names in order

### Requirement: v3 plugin switches migrate to the enabled list
Migrating a v3 directory SHALL set `plugins` to the names of the directories under `plugins/`
whose v3 `config.yaml` has `enabled: true`, sorted by name, and report them.

#### Scenario: Enabled v3 plugins
- **WHEN** a v3 directory has `plugins/AutoRole` with `enabled: true`, `plugins/Ticket` with
  `enabled: false` and `plugins/SQLiteAPI` without a config
- **THEN** the migrated config lists only AutoRole and the report names it
