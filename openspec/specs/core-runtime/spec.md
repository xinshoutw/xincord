# core-runtime Specification

## Purpose
Starts and stops the bot: the command line, the core files, plugin loading before connecting,
command uploads, the stop signals and the defaults every message uses.

## Requirements

### Requirement: Command line options
The `xincord` command SHALL accept `--level` (`-l`, a Python logging level name in any case,
default INFO), `--no-online` (`-N`) and `--force-renew-lang-resources` (`-Flang`). Unknown
options, `--token` among them, and level names SHALL be rejected with a usage message and
status 2.

#### Scenario: Defaults
- **WHEN** `xincord` runs without options
- **THEN** the level is INFO and both flags are off

#### Scenario: Every option
- **WHEN** `xincord -l debug -N -Flang` runs
- **THEN** the level is DEBUG and both flags are on

#### Scenario: Rejected options
- **WHEN** `xincord --ignore-update`, `xincord --token abc`, `xincord -t abc` or
  `xincord --level loud` runs
- **THEN** it prints a usage message and exits with status 2

### Requirement: Startup loads the configured plugins
On start the program SHALL load `config.yaml` from the working directory, writing the default if
missing, open the store at `data/xincord.db` and discover the plugins it lists. It SHALL log in with
a non-empty `XINCORD_TOKEN` environment variable, or else the configured token. Before the gateway
connects, the bot SHALL set the command translator and load the plugins. A config error, no token, a
rejected token or missing privileged intents SHALL be logged and end the program with status 1.

#### Scenario: Token precedence
- **WHEN** the config sets a token and the program starts with `XINCORD_TOKEN=abc`, with it
  empty and without it
- **THEN** it logs in with `abc`, and with the configured token in the other two cases

#### Scenario: Setup before connecting
- **WHEN** the bot's setup runs with a listed plugin
- **THEN** the plugin is loaded and the command translator is set

#### Scenario: Startup failures
- **WHEN** the config is invalid, no token is set, Discord rejects the token, or the privileged
  intents are not enabled for the application
- **THEN** the cause is logged, any opened store is closed and the exit status is 1

### Requirement: Offline check
With `--no-online` the program SHALL load the config and the listed plugins, which creates their
default files, without connecting to Discord and without needing a token. It SHALL exit with
status 0 if every listed plugin loaded and 1 otherwise.

#### Scenario: All plugins load
- **WHEN** `xincord --no-online` runs without a token and the config lists a plugin that loads
- **THEN** the plugin's files exist under `plugins/<Name>/`, nothing connects and the status is 0

#### Scenario: A plugin does not load
- **WHEN** a listed plugin is not installed, or fails in its setup
- **THEN** the exit status is 1

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

### Requirement: Graceful stop
SIGINT and SIGTERM SHALL close the bot, which unloads the plugins, then close the store, and the
program SHALL exit with status 0.

#### Scenario: Stop signal
- **WHEN** the running program receives SIGTERM or SIGINT
- **THEN** the plugins are unloaded, the store is closed and the exit status is 0

### Requirement: Mentions allow users only
Messages the bot sends SHALL by default ping only the mentioned users and the replied-to user;
`@everyone`, `@here` and role mentions SHALL NOT ping unless a message opts in.

#### Scenario: Default allowed mentions
- **WHEN** a bot is created
- **THEN** its allowed mentions permit users and the replied-to user and deny everyone and roles

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
It SHALL list several matches above the prompt as readline does and keep no lines free below the
prompt, so that log lines printed above it add no blank lines.

#### Scenario: Completing
- **WHEN** the owner presses Tab after `re` and after `reload A` while Alpha and Beta are loaded
- **THEN** `reload` and `Alpha` are offered

#### Scenario: No space kept for a menu
- **WHEN** the console shows its prompt on a terminal
- **THEN** the output moves the cursor to no line below or above the prompt's line

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

### Requirement: Status rotation
Once the bot is ready it SHALL show the configured activities in order, each for its `seconds`,
and start again after the last. A single activity SHALL be set once; no activities SHALL leave the
presence alone. Playing, listening, watching and competing SHALL use the text as the name,
streaming SHALL add its URL, and custom SHALL set a custom status. A failed update SHALL be logged
and the rotation SHALL go on. A full reload SHALL restart the rotation with the new list.

#### Scenario: Activity kinds
- **WHEN** each activity type is converted
- **THEN** it becomes the matching discord.py activity with the text, and the URL for streaming

#### Scenario: Rotation
- **WHEN** the bot is ready with two activities, with one, and with none
- **THEN** the first two alternate, the single one is set once, and the presence is not changed

#### Scenario: Failures and reload
- **WHEN** a presence update fails, and later a full reload changes the activities
- **THEN** the failure is logged and the next activity follows, and after the reload the new
  activities are shown

### Requirement: Interaction console lines
The bot SHALL log `[KIND] <user name>: <text>` for each slash command (`CMD`, with the command
string), message command (`MSG`, its name), button (`BTN`), string select (`STRING`), entity
select (`ENTITY`) and modal (`MODAL`); the text of components and modals SHALL be the custom ID.
Autocomplete and user commands SHALL NOT be logged.

#### Scenario: Console lines
- **WHEN** a slash command, a message command, a button, a string select, a user select, a modal,
  an autocomplete and a user command arrive from alice
- **THEN** the log has `[CMD] alice: /ping count: 2`, `[MSG] alice: Report`, `[BTN] alice: b`,
  `[STRING] alice: s`, `[ENTITY] alice: u` and `[MODAL] alice: m`, and nothing for the others

### Requirement: Interaction log channels
For each `interaction_log` target whose `types` include the interaction's type (`command`: slash
commands, `button`: buttons, `modal`: modals), the bot SHALL send the target's `format`, rendered
with the user keys, the interaction keys, `cl_type` (`CMD`, `BTN` or `MODAL`) and
`cl_interaction_string`, to the target channel. These messages SHALL NOT ping. A failed send SHALL
be logged without affecting the others; a full reload SHALL apply new targets.

#### Scenario: Matching targets
- **WHEN** one target lists `command` and `modal`, another `button`, and alice uses `/ping`, a
  button `b` and a modal `m`
- **THEN** the first channel gets ``[CMD] alice `/ping` `` and ``[MODAL] alice `m` ``, and the
  second gets ``[BTN] alice `b` ``

#### Scenario: No pings, failures and reload
- **WHEN** a format contains `%user_mention%`, one channel rejects the message, and a reload adds a
  target
- **THEN** no message allows mentions, the rejection is logged while the other channel still gets
  its line, and the next interaction also reaches the added target

### Requirement: No voice warnings at startup
The bot SHALL NOT log discord.py's warnings that PyNaCl or davey is missing: voice plays through a
Lavalink node, never through discord.py.

#### Scenario: No voice warnings
- **WHEN** a bot is created while discord.py would warn that PyNaCl and davey are missing
- **THEN** no warning about voice support is logged

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
