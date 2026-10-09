## Context

v3 reads `./config.yaml` with KAML in strict mode, exports the bundled default when the file is
missing, and keeps only three settings: the bot token, status strings, and console logger targets
(`XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/setting/SettingSerializer.kt`). Plugins load
`plugins/<Name>/config.yaml` the same way. Decision B6 asks for a new schema with pydantic v2,
warnings for unknown keys, and a v3 migration script.

## Goals / Non-Goals

**Goals:** one loader for the core and every plugin; a core schema that removes the v3 string
encoding; a migration the owner runs once per installation.

**Non-Goals:** reloading config at runtime (Core change `runtime`), plugin schemas, environment
variable overrides.

## Decisions

### Loader (`xincord.core.config`)

- `load_config(path, model, default)` returns a validated, frozen pydantic model. Models extend
  `xincord.core.config.Model` (`extra="allow"`, `frozen=True`), so unknown keys survive
  validation and are reported by walking `model_extra` through nested models, lists and tuples.
- Errors raise `ConfigError` with one line per problem: `<file>: <dotted.location>: <message>`.
  The plugin loader (Core change `plugin-loading`) catches it to disable only that plugin; the core
  config error stops startup.
- The default text is written only when the file is missing, so an operator's file is never
  replaced. Plugins pass their bundled default; the core default is
  `xincord/core/resources/config.yaml`.

### Core schema

```yaml
token: ""                 # the --token option overrides it (Core change runtime)
status:
  activities:
    - type: competing     # playing, streaming, listening, watching, custom, competing
      text: Developing...
      seconds: 5          # how long this activity is shown; default 5
      url: null           # required for streaming
interaction_log:          # forward interactions to channels; empty by default
  - guild_id: 123
    channel_id: 456
    types: [command, button, modal]
    format: "[%cl_type%] %user_name% `%cl_interaction_string%`"
```

Sequences are tuples so loaded configs are immutable.

### Migration (`xincord.core.migrate_v3`)

- `migrate_core_config(v3)` is pure: it returns the new mapping and report lines.
- `migrate_directory(root)` reads `root/config.yaml`, skips it when it has no `general_settings`
  key or when `config.v3.yaml` already exists, otherwise writes the backup first and then the new
  file. It returns report lines; `python -m xincord.core.migrate_v3 <dir>` prints them.
- v3 activity strings: `TYPE;text;ms`. For `STREAMING` the third field is the URL and an optional
  fourth field is the duration in milliseconds; without it the duration is the default.
- Plugin config migrations are added by each plugin's change.

### v3 behaved differently

- v3 behaved differently: unknown keys failed the whole load (KAML strict mode); they now warn.
- v3 behaved differently: a `STREAMING` status used its third field as both the URL and the delay,
  so `Thread.sleep` threw, nothing waited, and a list of only streaming entries spun the CPU
  (`StatusChanger.kt:72-90`). The URL and the duration are now separate fields.
- v3 behaved differently: malformed status strings were skipped on every cycle at runtime
  (`StatusChanger.kt:54-62`); they are now rejected when the config loads.
- v3 behaved differently: unknown console logger `log_type` values were ignored
  (`ConsoleLogger.kt:54-60`); they now fail validation.
- v3 behaved differently: the bundled default config contained a real guild and channel ID; the new
  default has no interaction log targets.

## Risks / Trade-offs

- A typo in a core key now only warns. The warning names the key, and the owner is the only
  operator (B6 note).

## User-visible changes

For the operator only: the core `config.yaml` uses the new keys above. Run
`python -m xincord.core.migrate_v3 <server dir>` once to convert a v3 file. Discord users see no
change.
