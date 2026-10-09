# Spec Delta

## ADDED Requirements

### Requirement: Reload follows the config
A full reload SHALL re-read the core config, unload in reverse order the loaded plugins that are
no longer listed or whose dependencies left, reload the loaded plugins that are still listed and
load the newly listed ones, in dependency order. A plugin whose reload fails SHALL keep its
previous version; a new plugin that needs missing intents SHALL be refused. The summary SHALL name
the plugins reloaded and those that failed. An invalid config SHALL change nothing.

#### Scenario: Config changed
- **WHEN** Alpha, Beta and Delta (which depends on Beta) are loaded and the config now lists
  Alpha, Delta and Gamma
- **THEN** Delta and then Beta are unloaded, Alpha is reloaded, Gamma is loaded, and the summary is
  `Reloaded: Alpha, Gamma. Failed: Delta (see the log).`

#### Scenario: Failures
- **WHEN** Alpha's new code fails, or a newly listed plugin needs intents the bot lacks
- **THEN** Alpha keeps running its previous version, the new plugin is not loaded, and both are
  named as failed

#### Scenario: Invalid config
- **WHEN** the config no longer validates
- **THEN** no plugin is unloaded, reloaded or loaded, and the summary starts with `Reload failed:`

### Requirement: Reload one plugin with its dependents
Reloading a named plugin SHALL reload it and the loaded plugins that depend on it, without
re-reading the core config. A plugin that is not loaded SHALL be reported in the summary.

#### Scenario: Named plugin
- **WHEN** Beta depends on Alpha and Alpha is reloaded by name
- **THEN** Alpha and Beta are reloaded and the summary is `Reloaded: Alpha, Beta.`

#### Scenario: Unknown plugin
- **WHEN** a plugin that is not loaded is named
- **THEN** nothing is reloaded and the summary is `Reload failed: plugin Ghost is not loaded`

### Requirement: Reloads upload the commands and never overlap
After a reload the bot SHALL upload the global and every guild's commands with force if it is
connected. A reload that starts while another runs SHALL wait for it to finish.

#### Scenario: Upload after reload
- **WHEN** a reload finishes while the bot is connected, and another while it is not
- **THEN** the first uploads every scope with force and the second uploads nothing

#### Scenario: Concurrent reloads
- **WHEN** two reloads start at the same time
- **THEN** the second plugin setup starts after the first one finished

### Requirement: Owner-only reload command
The bot SHALL register a global, guild-only `/xincord reload [plugin]` command that only
administrators see by default. Only the application's owner, or its team's admins and developers,
SHALL run it; anyone else SHALL get `Only the bot owner can use this command.` The reply SHALL be
ephemeral and carry the reload summary. The `plugin` option SHALL suggest the loaded plugins.

#### Scenario: Command payload
- **WHEN** the bot's commands are built
- **THEN** the global commands contain `xincord` with a `reload` subcommand, no DM permission and
  default member permissions 0

#### Scenario: Owner and others
- **WHEN** the owner and another member run `/xincord reload`
- **THEN** the owner gets the summary and the other member gets the refusal without a reload

#### Scenario: Plugin suggestions
- **WHEN** the owner types `al` into the `plugin` option while Alpha and Beta are loaded
- **THEN** Alpha is suggested

### Requirement: SIGHUP reloads
SIGHUP SHALL run a full reload while the bot runs, and the summary SHALL be logged.

#### Scenario: Hang-up signal
- **WHEN** the running program receives SIGHUP after a plugin was added to the config
- **THEN** that plugin is loaded and the bot keeps running
