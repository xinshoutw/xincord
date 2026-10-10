## ADDED Requirements

### Requirement: CustomCommands' v3 switch file is set aside
Migrating a v3 directory SHALL rename `plugins/CustomCommands/config.yaml` to `config.v3.yaml` when
it holds no key but `enabled` (SimpleCommand's file, moved there), after writing the new core
config, and report it, so that the plugin writes its bundled commands at its first load. A file
with other keys, or one with a `config.v3.yaml` beside it, SHALL stay as it is.

#### Scenario: Switch file set aside
- **WHEN** a v3 directory whose `plugins/SimpleCommand/config.yaml` holds `enabled: true` is
  migrated
- **THEN** `plugins/CustomCommands/config.v3.yaml` holds that text, no `config.yaml` is left
  there, the core config lists CustomCommands and the report names both files

#### Scenario: Other files stay
- **WHEN** `plugins/CustomCommands/config.yaml` lists commands, or a `config.v3.yaml` exists
  beside a switch file
- **THEN** the file stays, and for the second the report says why
