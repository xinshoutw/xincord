## MODIFIED Requirements

### Requirement: Commands are uploaded when ready
When the bot is ready it SHALL upload the global commands and then each guild's commands: with
force at the first READY after the program started, so that a restart repairs commands that
another program changed, and at later READYs each only if its payload changed since the last
upload. When the bot joins a guild it SHALL upload that guild's commands even if they did not
change.

#### Scenario: Ready
- **WHEN** the bot becomes ready in two guilds, and again after a new session
- **THEN** the global commands and both guilds' commands are synced with force the first time and
  without forcing the second time

#### Scenario: Joined guild
- **WHEN** the bot joins a guild
- **THEN** that guild's commands are synced with force

### Requirement: Reloads upload the commands and never overlap
After a reload the bot SHALL log the summary and then, if it is connected, upload the global and
each guild's commands whose payload changed since their last upload, also after a failed reload
that unloaded plugins. A reload that starts while another runs SHALL log `Waiting for the running
reload to finish` and wait for it to finish.

#### Scenario: Upload after reload
- **WHEN** a reload finishes while the bot is connected, and another while it is not
- **THEN** the first syncs every scope without force and the second syncs nothing

#### Scenario: Summary before the upload
- **WHEN** a reload finishes while the bot is connected
- **THEN** its summary is logged before the first upload starts

#### Scenario: Upload after a reload that unloaded a plugin
- **WHEN** a reload of one plugin fails and unloads it while the bot is connected
- **THEN** every scope is synced without force, without that plugin's commands

#### Scenario: Concurrent reloads
- **WHEN** two reloads start at the same time
- **THEN** the second plugin setup starts after the first one finished

#### Scenario: Waiting reload
- **WHEN** a reload starts while another runs
- **THEN** `Waiting for the running reload to finish` is logged once
