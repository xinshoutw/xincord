## Why

The owner runs the bot in a terminal (and later under `docker compose attach`) and needs to
reload and stop it there. v3's JLine console (`JLineManager.kt`) offered `reload` and
`stop` / `exit` / `shutdown` with command completion, and printed log lines above the prompt
(`JLineLogbackAppender.kt`). Decision B15 keeps it as a prompt_toolkit console.

## What Changes

- A console with the prompt `console > ` when stdin and stdout are terminals: `reload` and
  `reload <plugin>` call `Bot.reload`; `stop`, `exit`, `shutdown` and ^D stop the bot like SIGTERM;
  ^C is logged and ignored; anything else is logged as an unknown command.
- Completion of the command names and, after `reload`, of the loaded plugins.
- Log lines print above the prompt: `main` sets up logging inside prompt_toolkit's
  `patch_stdout`.
- New dependency `prompt-toolkit` (BSD-3-Clause).

Ported from:
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/cli/JLineManager.kt:12-94`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/JLineLogbackAppender.kt:8-32`
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/Main.kt:27-28`

Out of scope: the container settings that give the console a terminal (Core change `container`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-runtime`: the interactive console.

## Impact

New module `xincord.core.console`; `xincord.core.cli` starts it and wraps logging in
`patch_stdout`. New runtime dependency `prompt-toolkit>=3.0.53`.
