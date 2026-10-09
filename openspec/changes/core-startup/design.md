## Context

v3 starts in `Main.kt`: Clikt parses the options, `SettingsLoader` reads `./config.yaml`,
`BotLoader.start` builds JDA with the plugins' intents and waits until it is ready, then loads the
plugins and uploads the commands (`ListenerManager`). The program ends when the console says
`stop`. xincord already has the pieces: `load_config` and `CoreConfig`, `Store`, `discover`, the
`Bot` with `load_plugins`, and `CommandTree.sync_global` / `sync_guild`.

## Goals / Non-Goals

**Goals:** a `xincord` command that starts the bot from the working directory, an offline check,
command uploads on ready and on guild join, a clean stop on SIGINT and SIGTERM, and B19's
allowed mentions.

**Non-Goals:** the console, SIGHUP and `/xincord reload` (`core-console`); status rotation and the
interaction log (`core-status-log`); the container (`container`).

## Decisions

- **Entry point.** `xincord.core.cli:main(argv)` returns the exit status and is installed as the
  `xincord` console script; `python -m xincord.core.cli` works too. `parse_args` returns a frozen
  `Options`, and `run(options)` holds the async lifecycle, so tests drive it without touching the
  logging setup.
- **Paths.** Everything is relative to the working directory, as in v3: `config.yaml`,
  `plugins/<Name>/` and the store at `data/xincord.db`. The `data/` directory holds only the
  database, so the container can mount a named volume there (B16).
- **Logging.** `discord.utils.setup_logging(level=..., root=True)`: discord.py's formatter on
  stderr, coloured on a terminal. No log file: Docker keeps the stream.
- **Levels.** Python's level names in any case (`logging.getLevelNamesMapping()`), so `WARN` still
  works; anything else is a usage error.
- **Plugins load in `setup_hook`.** discord.py runs it after logging in and before the gateway
  connects, so every command exists before `on_ready` uploads them. `setup_hook` first sets the
  `Translator`, then calls `load_plugins`. A plugin's `setup` therefore sees empty guild caches;
  work that needs them waits for `bot.wait_until_ready()` or `on_ready`.
- **Uploads.** `on_ready` calls `sync_global`, then `sync_guild` for each guild in `bot.guilds`;
  `on_guild_join` calls `sync_guild(force=True)`. `on_ready` can fire again after a reconnect;
  unchanged payloads then cost one hash comparison per scope.
- **Offline check.** `--no-online` runs the same `setup_hook` inside `async with bot` without
  logging in, compares `bot.loaded` with the configured list and exits; closing the bot unloads
  the plugins again. No token is needed.
- **Stop signals.** `loop.add_signal_handler` for SIGINT and SIGTERM schedules `bot.close()`.
  `bot.start` returns once the bot is closed; `run` then awaits the same close so it finishes,
  removes the handlers and closes the store. discord.py's `commands.Bot.close` unloads the
  extensions before the connection closes. Signal handlers need a Unix event loop; the bot runs
  on macOS and in Linux containers.
- **Failures.** Config errors, an empty token, `LoginFailure` and `PrivilegedIntentsRequired` are
  logged with their message (no traceback) and return status 1. Other errors propagate with a
  traceback.
- **Allowed mentions.** The bot is created with
  `AllowedMentions(everyone=False, users=True, roles=False, replied_user=True)`; a message opts in
  with its own `allowed_mentions`.
- **Removed options.** `--ignore-update` (`-I`; no version check, B15) and
  `--auto-defer-interactions` / `--no-auto-defer-interactions` (commands opt out of the defer
  through `extras["defer"]`, B5).

### v3 behaved differently

- v3 behaved differently: `--no-online` read the core config and then idled with the console
  open; the plugins were never loaded and their files were not created.
- v3 behaved differently: log levels were logback names, and an unknown name silently became
  DEBUG.
- v3 behaved differently: logs were also written to `log/output.log`, rotated at 1 MB.
- v3 behaved differently: plugins loaded after JDA was ready, so their setup could read the guild
  cache; xincord loads them before the gateway connects.
- v3 behaved differently: the missing-token check compared the token with a placeholder string;
  xincord's default token is empty.
- v3 behaved differently: guild commands were uploaded at startup only when there were any, so
  removing the last guild command left stale commands in every guild; an empty payload is now
  uploaded once.
- v3 behaved differently: JDA's defaults let every mention ping, including `@everyone` and roles.

## Risks / Trade-offs

- A plugin that reads guilds in `setup` sees none. The port-plugin checklist and the porting guide
  name the alternatives.
- No log file: logs of a recreated container are gone. A rotating file handler under `data/` can
  be added if the owner wants it.

## User-visible changes

1. The bot starts with `xincord [-t TOKEN] [-l LEVEL] [-N] [-Flang]`. `--ignore-update` (`-I`) and
   `--auto-defer-interactions` / `--no-auto-defer-interactions` are rejected.
2. `--no-online` checks the config and the plugins (creating their files) and exits with 0 when
   all loaded and 1 otherwise, instead of idling.
3. Logs go to stderr only; there is no `log/output.log`.
4. Level names follow Python: DEBUG, INFO, WARNING (or WARN), ERROR, CRITICAL.
5. The database file is `data/xincord.db`.
6. Bot messages no longer ping `@everyone`, `@here` or roles unless a feature opts in (B19).
