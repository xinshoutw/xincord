## MODIFIED Requirements

### Requirement: Hot reload follows dependencies and intents
Reloading a plugin SHALL reload it and then every loaded plugin that depends on it, in load order.
A failed reload SHALL keep the previous version and stop; the previous version SHALL get the
config, lang and templates it loaded, not the files that broke the new one. When it fails too, the
plugin and the plugins that depend on it SHALL be unloaded, and the error SHALL say so. A hot load
SHALL be refused when the plugin needs intents the bot lacks or a dependency that is not loaded.

#### Scenario: Reload with dependents
- **WHEN** Alpha is reloaded and Beta depends on Alpha
- **THEN** Alpha's and then Beta's setup run again and the reload reports both

#### Scenario: Failed reload keeps the previous version
- **WHEN** Alpha's setup raises during a reload
- **THEN** the reload fails naming Alpha and Alpha's previous version stays loaded

#### Scenario: Broken files keep the previous version
- **WHEN** Alpha's `config.yaml`, lang files or templates no longer validate and Alpha is reloaded
- **THEN** the reload fails naming the file, and Alpha's previous version runs its setup again
  with the config, lang and templates it had

#### Scenario: Previous version fails too
- **WHEN** a reload fails and Alpha's previous version fails again, as when a file that Alpha
  reads itself is gone, and Beta depends on Alpha
- **THEN** Alpha and Beta are unloaded, with nothing of them left in the bot and its modules, the
  error names both and says that a full reload loads them, and a full reload loads both again once
  the file is back

#### Scenario: Moved plugin
- **WHEN** Alpha's entry point names another module than the one Alpha loaded from, and the bot
  reloads
- **THEN** Alpha's reload fails with an error, and its previous version keeps running with its
  routes

#### Scenario: Hot load needs the intents
- **WHEN** a plugin that needs the members intent, or one whose dependency is not loaded, is loaded
  after startup on a bot created without it
- **THEN** loading is refused and the message says what is missing
