## MODIFIED Requirements

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
