# Spec Delta

## ADDED Requirements

### Requirement: Console commands
The console SHALL show the prompt `console > ` and read one command per line, matching command
names in any case. `reload` SHALL run a full reload and `reload <plugin>` a reload of that plugin.
`stop`, `exit`, `shutdown` and end of input (^D) SHALL stop the bot as SIGTERM does and end the
console. ^C SHALL be logged and ignored, blank lines ignored, and anything else logged as an
unknown command.

#### Scenario: Reload commands
- **WHEN** the owner types `reload`, `RELOAD Alpha`, an empty line and `frobnicate`
- **THEN** a full reload and a reload of Alpha run, and `Unknown command: frobnicate` is logged

#### Scenario: Stopping
- **WHEN** the owner types `stop`, `EXIT` or `shutdown`, or presses ^D
- **THEN** the bot is asked to stop once and the console ends

#### Scenario: Interrupt
- **WHEN** the owner presses ^C and then types `stop`
- **THEN** the interrupt is logged and the console keeps reading until `stop`

### Requirement: Console completion
The console SHALL complete the command names and, after `reload`, the names of the loaded plugins.

#### Scenario: Completing
- **WHEN** the owner presses Tab after `re` and after `reload A` while Alpha and Beta are loaded
- **THEN** `reload` and `Alpha` are offered

### Requirement: Console only on a terminal
The program SHALL run the console while the bot runs only when stdin and stdout are terminals and
`--no-online` is not set. With a console, logging SHALL write through prompt_toolkit's stdout
proxy so that log lines appear above the prompt. The console SHALL end when the bot stops.

#### Scenario: Terminal detection
- **WHEN** `xincord` starts with and without terminals
- **THEN** with terminals the logging is set up inside `patch_stdout` and the console runs;
  without them neither happens

#### Scenario: Stop from the console
- **WHEN** the running program's console reads `stop`
- **THEN** the plugins are unloaded, the store is closed and the exit status is 0

#### Scenario: Stopped elsewhere
- **WHEN** SIGTERM stops the bot while the console waits for input
- **THEN** the console ends and the exit status is 0
