## ADDED Requirements

### Requirement: No voice warnings at startup
The bot SHALL NOT log discord.py's warnings that PyNaCl or davey is missing: voice plays through a
Lavalink node, never through discord.py.

#### Scenario: No voice warnings
- **WHEN** a bot is created while discord.py would warn that PyNaCl and davey are missing
- **THEN** no warning about voice support is logged

## MODIFIED Requirements

### Requirement: Reloads upload the commands and never overlap
After a reload the bot SHALL log the summary and then, if it is connected, upload the global and
every guild's commands with force, also after a failed reload that unloaded plugins. A reload that
starts while another runs SHALL log `Waiting for the running reload to finish` and wait for it to
finish.

#### Scenario: Upload after reload
- **WHEN** a reload finishes while the bot is connected, and another while it is not
- **THEN** the first uploads every scope with force and the second uploads nothing

#### Scenario: Summary before the upload
- **WHEN** a reload finishes while the bot is connected
- **THEN** its summary is logged before the first upload starts

#### Scenario: Upload after a reload that unloaded a plugin
- **WHEN** a reload of one plugin fails and unloads it while the bot is connected
- **THEN** every scope is uploaded with force, without that plugin's commands

#### Scenario: Concurrent reloads
- **WHEN** two reloads start at the same time
- **THEN** the second plugin setup starts after the first one finished

#### Scenario: Waiting reload
- **WHEN** a reload starts while another runs
- **THEN** `Waiting for the running reload to finish` is logged once

### Requirement: Console completion
The console SHALL complete the command names and, after `reload`, the names of the loaded plugins.
It SHALL list several matches above the prompt as readline does and keep no lines free below the
prompt, so that log lines printed above it add no blank lines.

#### Scenario: Completing
- **WHEN** the owner presses Tab after `re` and after `reload A` while Alpha and Beta are loaded
- **THEN** `reload` and `Alpha` are offered

#### Scenario: No space kept for a menu
- **WHEN** the console shows its prompt on a terminal
- **THEN** the output moves the cursor to no line below or above the prompt's line
