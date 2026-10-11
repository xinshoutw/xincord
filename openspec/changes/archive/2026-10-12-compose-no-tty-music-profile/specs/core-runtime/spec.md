## ADDED Requirements

### Requirement: Plain log lines off a terminal
Logging SHALL colour its lines only when stderr is a terminal. Otherwise, as in a container without
a TTY, each line SHALL be plain text without escape sequences: the time, the level, the logger's
name and the message.

#### Scenario: Log without a terminal
- **WHEN** `xincord` starts with a stderr that is not a terminal
- **THEN** logging is set up with a plain formatter, whose line for an INFO record holds the time,
  `INFO`, the logger's name and the message, and no escape character

#### Scenario: Log on a terminal
- **WHEN** `xincord` starts with stderr on a terminal
- **THEN** logging keeps discord.py's colour formatter
