# core-runtime Specification

## Purpose
Starts and stops the bot: the command line, the core files, plugin loading before connecting,
command uploads, the stop signals and the defaults every message uses.

## Requirements

### Requirement: Command line options
The `xincord` command SHALL accept `--token` (`-t`), `--level` (`-l`, a Python logging level name
in any case, default INFO), `--no-online` (`-N`) and `--force-renew-lang-resources` (`-Flang`).
Unknown options and level names SHALL be rejected with a usage message and status 2.

#### Scenario: Defaults
- **WHEN** `xincord` runs without options
- **THEN** no token is given, the level is INFO and both flags are off

#### Scenario: Every option
- **WHEN** `xincord -t abc -l debug -N -Flang` runs
- **THEN** the token is `abc`, the level is DEBUG and both flags are on

#### Scenario: Rejected options
- **WHEN** `xincord --ignore-update` or `xincord --level loud` runs
- **THEN** it prints a usage message and exits with status 2

### Requirement: Startup loads the configured plugins
On start the program SHALL load `config.yaml` from the working directory, writing the default when
it is missing, open the store at `data/xincord.db` and discover the plugins listed under `plugins`.
It SHALL log in with `--token`, or else the configured token. Before the gateway connects, the bot
SHALL set the command translator and load the plugins. A config error, an empty token, a rejected
token or missing privileged intents SHALL be logged and end the program with status 1.

#### Scenario: Token precedence
- **WHEN** the config sets a token and the program starts with and without `--token abc`
- **THEN** it logs in with `abc`, and with the configured token without the option

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
When the bot is ready it SHALL upload the global commands and then each guild's commands, each only
if its payload changed since the last upload. When the bot joins a guild it SHALL upload that
guild's commands even if they did not change.

#### Scenario: Ready
- **WHEN** the bot becomes ready in two guilds
- **THEN** the global commands and both guilds' commands are synced without forcing

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
