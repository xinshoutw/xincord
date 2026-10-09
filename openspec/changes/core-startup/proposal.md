## Why

The core has its building blocks but nothing that starts the bot. In v3, `Main.kt`,
`Arguments.kt`, `SettingsLoader.kt`, `BotLoader.kt` and `ListenerManager.kt` parse the command
line, read the core config, build JDA with the plugins' intents, upload the commands and stop the
program. Decision B15 fixes the command line options and B19 the default allowed mentions.

## What Changes

- A `xincord` command (`xincord.core.cli:main`) with `--token` (`-t`), `--level` (`-l`),
  `--no-online` (`-N`) and `--force-renew-lang-resources` (`-Flang`).
- Startup in the working directory: load or create `config.yaml`, open `data/xincord.db`, discover
  the plugins listed under `plugins`, set the command translator and load the plugins before the
  gateway connects. A config error, a missing or rejected token, or missing privileged intents
  end the program with status 1.
- `--no-online` loads the config and the plugins without connecting, then exits with a status that
  says whether every listed plugin loaded.
- The commands are uploaded when the bot is ready (global, then each guild, only when changed) and
  forced for a guild the bot joins.
- SIGINT and SIGTERM close the bot and the store, then exit with status 0.
- Messages ping users (and the replied-to user) only, unless a message opts in.

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/Main.kt:17-39`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/Arguments.kt:11-60`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/SettingsLoader.kt:21-33`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:36-107`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:18-36`

Out of scope: the interactive console, SIGHUP and `/xincord reload` (Core change `core-console`);
status rotation and the interaction log (Core change `core-status-log`); the Docker image (Core
change `container`); the `/bot-info` source link (C3), which the BotInfo plugin will own.

## Capabilities

### New Capabilities

- `core-runtime`: the command line, startup and shutdown, command uploads and the default allowed
  mentions.

### Modified Capabilities

None.

## Impact

New module `xincord.core.cli` and a `xincord` console script; `Bot` gains `setup_hook`, `on_ready`,
`on_guild_join` and default allowed mentions. No new dependencies.
