## MODIFIED Requirements

### Requirement: Hot reload follows dependencies and intents
Reloading a plugin SHALL reload it and then every loaded plugin that depends on it, in load order;
a failed reload SHALL keep the previous version and stop, and the previous version SHALL get the
config and lang that it loaded before, not the files that broke the new one. When the previous
version fails too, the plugin SHALL be unloaded and the error SHALL say so. Loading a plugin after
startup SHALL be refused when it needs intents the bot lacks, or a dependency that is not loaded.

#### Scenario: Reload with dependents
- **WHEN** Alpha is reloaded and Beta depends on Alpha
- **THEN** Alpha's and then Beta's setup run again and the reload reports both

#### Scenario: Failed reload keeps the previous version
- **WHEN** Alpha's setup raises during a reload
- **THEN** the reload fails naming Alpha and Alpha's previous version stays loaded

#### Scenario: Broken files keep the previous version
- **WHEN** Alpha's `config.yaml` or lang files no longer validate and Alpha is reloaded
- **THEN** the reload fails naming the file, and Alpha's previous version runs its setup again
  with the config and lang it had

#### Scenario: Previous version fails too
- **WHEN** a reload fails and Alpha's previous version fails again, as when a file that Alpha
  reads itself is gone
- **THEN** Alpha is unloaded, with nothing of it left in the bot, the error says so, and loading
  Alpha again works once the file is back

#### Scenario: Hot load needs the intents
- **WHEN** a plugin that needs the members intent, or one whose dependency is not loaded, is loaded
  after startup on a bot created without it
- **THEN** loading is refused and the message says what is missing
