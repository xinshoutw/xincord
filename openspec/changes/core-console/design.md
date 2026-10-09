## Context

v3 started `JLineManager` after the bot (`Main.kt:27`): a JLine reader with the prompt
`console > `, first-word completion of `reload`, `stop`, `exit` and `shutdown`, and a logback
appender that printed log lines above the prompt. `reload` restarted the runtime, the stop words
and ^D completed the stop signal, ^C was logged. xincord's reload (`Bot.reload`) and stop path
(`cli._serve`'s SIGTERM handler) exist already.

## Goals / Non-Goals

**Goals:** v3's console commands on top of `Bot.reload` and the existing stop path, readable log
output while typing, and no console when there is no terminal.

**Non-Goals:** new console commands beyond `reload <plugin>`; the container's terminal settings.

## Decisions

- **Module.** `xincord.core.console.run_console(bot, stop)` loops over
  `PromptSession.prompt_async("console > ")`. It never closes the bot itself: the stop words and
  ^D call the `stop` callback that SIGINT and SIGTERM use, then return.
- **Matching.** The first word is compared in lower case (`RELOAD` works as in v3); plugin names
  keep their case because `Bot.reload` matches them exactly. `reload` takes at most one plugin.
- **Completion.** `completer(bot)` builds a `NestedCompleter` with the command names and the
  loaded plugins under `reload`; it is rebuilt before each prompt, so plugins loaded by a reload
  complete too.
- **^C and ^D.** While the prompt waits, the terminal is in raw mode, so ^C reaches prompt_toolkit
  as a key and raises `KeyboardInterrupt` (no SIGINT): it is logged and the prompt shows again.
  ^D on an empty line raises `EOFError` and stops the bot.
- **Terminal detection.** `main` enables the console when stdin and stdout are terminals and
  `--no-online` is not set, and passes `console=True` to `run`.
- **Logging above the prompt.** `main` enters `patch_stdout(raw=True)` before
  `discord.utils.setup_logging`, so the log handler's stream is prompt_toolkit's proxy, which
  prints above the prompt; `raw=True` keeps discord.py's colour codes.
- **Lifetime.** `_serve` starts the console task inside `async with bot` and cancels it once the
  bot has closed, so a stop from SIGTERM also ends the prompt.
- **Tests** drive the console through `create_pipe_input()` and `DummyOutput()` inside
  `create_app_session`.

### v3 behaved differently

- v3 behaved differently: the console started whether or not stdin was a terminal, and end of
  input stopped the bot; xincord runs the console only on a terminal.
- v3 behaved differently: `reload` took no plugin name and completion covered the command names
  only.

## Risks / Trade-offs

- prompt_toolkit's proxy flushes from a background thread; log lines written by other threads
  (the storage worker never logs) still pass through it.

## User-visible changes

For the operator, in the terminal:

1. Same commands as v3: `reload`, `stop`, `exit`, `shutdown` (any case), ^D stops, ^C is logged
   (`Interrupted by user: ^C`) and ignored, other input logs `Unknown command: <text>`.
2. New: `reload <plugin>` reloads one plugin with its dependents, and Tab completes the loaded
   plugin names after `reload`.
3. The console appears only when the bot runs in a terminal (under compose:
   `docker compose attach`, set up by the container change).
