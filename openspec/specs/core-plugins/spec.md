# core-plugins Specification

## Purpose
Finds the plugins the operator enabled, loads them in dependency order with the intents they
need, keeps one broken plugin from affecting the others, gives each plugin its files under
`plugins/<Name>/`, reloads plugins together with the plugins that depend on them, and relays to
them the gateway events that discord.py does not parse.

## Requirements

### Requirement: Plugins are discovered through entry points
The core SHALL find installed plugins in the entry-point group `xincord.plugins`, keyed by plugin
name, and consider only the names in the core config's `plugins` list. Metadata SHALL come from the
module constants `DEPENDS` and `SOFT_DEPENDS` (tuples of plugin names, default empty) and `INTENTS`
(default none). A name that is not installed, a module that fails to import and invalid metadata
SHALL each leave out only that plugin, with an error naming it.

#### Scenario: Enabled plugins are discovered
- **WHEN** plugins Alpha and Beta are installed and only Alpha is enabled
- **THEN** discovery returns Alpha with its declared dependencies and intents

#### Scenario: Broken plugins are left out
- **WHEN** one enabled name is not installed, another plugin fails to import, and a third declares
  `DEPENDS` as a string
- **THEN** discovery returns the other plugins and logs an error naming each broken one

### Requirement: Plugins load in dependency order
Plugins SHALL load after their dependencies and after their enabled soft dependencies. A plugin
whose dependency is not enabled or cannot load, or whose dependencies form a cycle, SHALL be left
out together with every plugin that depends on it.

#### Scenario: Dependencies first
- **WHEN** Gamma depends on Beta, Beta soft-depends on Alpha, and they are enabled as Gamma, Beta,
  Alpha
- **THEN** they are ordered Alpha, Beta, Gamma

#### Scenario: Missing dependencies and cycles
- **WHEN** Delta depends on a plugin that is not enabled, Epsilon depends on Delta, and Zeta and
  Eta depend on each other
- **THEN** none of those four load and the remaining plugins do

### Requirement: Intents are aggregated before connecting
The bot's intents SHALL be discord.py's default intents plus the `INTENTS` of every plugin that
discovery kept, fixed when the bot is created.

#### Scenario: Plugin intents are added
- **WHEN** one plugin needs the members intent and another the message content intent
- **THEN** the bot's intents include both and the default intents

### Requirement: A failing plugin disables only itself
When a plugin raises while loading (in its module, its setup, or its config, lang or template
files), the core SHALL log the error with the plugin's name, leave that plugin and every plugin
that depends on it unloaded, and keep loading the others.

#### Scenario: One plugin fails
- **WHEN** Beta's setup raises and Gamma depends on Beta, among Alpha, Beta, Gamma and Delta
- **THEN** Alpha and Delta load, Beta and Gamma do not, and the log names Beta and Gamma

### Requirement: Plugin files live under plugins/<Name>/
Each plugin SHALL get a context with its directory `plugins/<Name>/`, the shared store, its
`config.yaml` (created from the plugin's bundled default, then validated against the plugin's
model) and its lang files (exported from the bundle where missing, all replaced when lang renewal
is forced, then loaded).

#### Scenario: First load creates the files
- **WHEN** a plugin with a bundled `config.yaml` and lang directory loads for the first time
- **THEN** `plugins/<Name>/config.yaml` and its lang files exist and the plugin receives the parsed
  config and lang

#### Scenario: Edited files are kept unless renewal is forced
- **WHEN** the plugin's config and a lang file were edited and the plugin loads again
- **THEN** the edits are kept, and only forced renewal replaces the lang file

#### Scenario: Broken config disables the plugin
- **WHEN** `plugins/<Name>/config.yaml` does not match the plugin's model
- **THEN** that plugin does not load and the error names the file

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

### Requirement: Plugins receive gateway events that discord.py does not parse
`Bot.relay_gateway_event(name)` SHALL make the bot dispatch every gateway event `name` it receives
as `gateway_<name in lower case>`, with Discord's payload as the only argument, after discord.py's
own handling of that event when it has one. Relaying the same event again SHALL change nothing,
and the relay SHALL last as long as the bot.

#### Scenario: An event discord.py does not parse
- **WHEN** a plugin relays `VOICE_CHANNEL_STATUS_UPDATE` twice and the gateway delivers one
- **THEN** the listeners of `gateway_voice_channel_status_update` receive its payload once

#### Scenario: An event discord.py parses
- **WHEN** an event that discord.py already parses is relayed and delivered
- **THEN** discord.py's handling runs first, and the listeners receive the same payload

### Requirement: Plugins get a data directory
Each plugin's context SHALL name `<data>/<Name>/` as the plugin's data directory, for the files
that the plugin keeps itself, where `<data>` is the data directory that the bot was given; the
program SHALL give `data/`, which also holds the store's database. The core SHALL NOT create the
plugin's directory.

#### Scenario: Data directory
- **WHEN** a plugin loads in a bot whose data directory is `data`
- **THEN** its context's data directory is `data/<Name>`, which does not exist until the plugin
  creates it

#### Scenario: Data directory at startup
- **WHEN** the program starts with a listed plugin
- **THEN** the plugin's data directory is `data/<Name>` in the working directory
