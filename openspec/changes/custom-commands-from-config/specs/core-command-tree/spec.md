## MODIFIED Requirements

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
