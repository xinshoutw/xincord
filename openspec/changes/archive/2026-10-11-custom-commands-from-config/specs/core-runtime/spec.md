## MODIFIED Requirements

### Requirement: Reloads upload the commands and never overlap
After a reload the bot SHALL upload the global and every guild's commands with force if it is
connected, also after a failed reload that unloaded plugins. A reload that starts while another
runs SHALL wait for it to finish.

#### Scenario: Upload after reload
- **WHEN** a reload finishes while the bot is connected, and another while it is not
- **THEN** the first uploads every scope with force and the second uploads nothing

#### Scenario: Upload after a reload that unloaded a plugin
- **WHEN** a reload of one plugin fails and unloads it while the bot is connected
- **THEN** every scope is uploaded with force, without that plugin's commands

#### Scenario: Concurrent reloads
- **WHEN** two reloads start at the same time
- **THEN** the second plugin setup starts after the first one finished
