# Porting guide: XsDiscordBotKt to xincord

How Kotlin/JDA concepts map to Python/discord.py in this project, which ideas from the abandoned
v4 rewrite are kept, the traps found so far, and every place where xincord deliberately behaves
differently from v3. Update it after each Core change and each plugin.

Baseline: XsDiscordBotKt `main` at `3a59607` (v3.4). Decisions: `docs/porting/decisions.md`.

## Concept mapping

| Kotlin / JDA (v3) | Python / discord.py (xincord) | Decision |
|---|---|---|
| Plugin jar + `info.yaml`, classloader per plugin | extension module + `commands.Cog`, metadata as module constants, entry point in group `xincord.plugins` | B2, B3 |
| "API plugins" (SQLiteAPI, GoogleSheetAPI, AudioAPI) | ordinary dependencies or nothing | B12 |
| Load order from `depend` / `soft_depend` | `graphlib.TopologicalSorter`; a failing plugin disables only itself | B3 |
| `GatewayIntent` presets | `discord.Intents` aggregated from enabled plugins before connecting | B4 |
| `ListenerAdapter` overrides | `@commands.Cog.listener()` | B3 |
| `CommandData` / `SlashCommandData` | `app_commands.command` / `app_commands.Group` | B5 |
| InteractionLogger's blanket `deferReply(true)` | the command tree defers ephemerally; modal commands opt out through `extras` | B5 |
| Command localization via `StringLocalizer` and Kotlin property paths | `app_commands.Translator` fed from `lang/<locale>/register.yaml` keys | B7 |
| `MessageCreator` YAML templates | templates module: v1 YAML tags and Components V2 | B10 |
| `Placeholder` / commons-text substitutor | single-level `%key%` substitution with a fresh context per render | B10 |
| `ComponentIdManager` (`{prefix}{a..z}:{value};...`) | new versioned ID format plus a permanent legacy decoder | B9 |
| JSON files and embedded MongoDB | SQLite (`sqlite3` + `asyncio.to_thread`), key-value table plus per-plugin tables | B8 |
| kotlinx/Jackson YAML config | pydantic v2 models over PyYAML; unknown keys warn | B6 |
| Coroutines, `launch`, scheduled executors | `asyncio` tasks, `discord.ext.tasks.loop` | |
| JLine console, `--ignore-update` | prompt_toolkit console, SIGHUP reload, `/xincord reload`; no version check | B15 |
| Ktor Web-Dashboard | not ported | B13 |

## Intents kept from the v4 attempt (A3)

The v4 design spec stays in the old repository
(`XsDiscordBotKt@3a59607:docs/specs/2026-04-07-v4-core-refactor-design.md`); the branch analysis
is `docs/porting/analysis/research/v4-branch.md`. Kept:

- Plugins declare their surface (commands, components, listeners, load and unload hooks) instead
  of filtering every event themselves.
- Exact command-path dispatch: discord.py's tree already routes groups and subcommands; test that
  every command path has a callback.
- Prefix-routed persistent components that survive restarts (`discord.ui.DynamicItem`).
- Typed config models with defaults, validated at startup, failing loudly per plugin.
- Command localization from flat YAML keys; a missing name or description fails at startup instead
  of falling back to an empty string.
- A plugin manifest with dependencies and intents, sorted topologically, with a check for missing
  dependencies.

Rejected: a DI container (pass a small context object instead), classloader isolation, deferring
every component interaction centrally (it blocks modals), rewriting the template schema without
migrating the shipped YAML, silent fallbacks, reload as a full gateway reconnect, and two listener
styles at once.

## Pitfalls

- **Annotations at import time.** discord.py evaluates app-command parameter annotations when the
  decorator runs (PEP 649/749 make annotations lazy, but discord.py resolves them eagerly). Keep
  those imports at runtime; see `runtime-evaluated-decorators` in `pyproject.toml`.
- **Deprecation warnings.** pytest turns warnings into errors. discord.py 2.7.1 calls the
  deprecated `asyncio.iscoroutinefunction`; filter that warning when discord.py is added.
- **Member removal.** `on_member_remove` fires only for cached members; use
  `on_raw_member_remove`.
- **Channel overwrites.** `create_text_channel(overwrites=...)` does not inherit the category's
  overwrites the way JDA does; merge them explicitly (Ticket).
- **IntervalPusher.** `tasks.loop` schedules from each start, not after each completion as Kotlin
  did. discord.py has no REST ping; time `GET /users/@me` to keep `%ping%`.
- **BasicCalculator.** `decimal` defaults to 28 digits; use `Fraction` or exact decimal arithmetic.
  The golden files in `docs/porting/analysis/inventory/fixtures/` decide.
- **Lookup keys.** Kotlin's `StringLocalizer` uses camelCase property paths; Python uses the YAML
  keys directly.
- **CJK in tests.** Build samples with `chr(0x4E2D)` or YAML fixtures. Agent tools may decode a
  typed `\u` escape into the real character, which the CJK hook then rejects.
- **prek pygrep** compiles patterns as bytes, so a `\u` escape in a pattern fails; match UTF-8 byte
  ranges instead.
- **Global `core.hooksPath`.** prek refuses to install while a global `core.hooksPath` is set; use
  `git config --local core.hooksPath .git/hooks`.

v3 behaviors never to reproduce: loading plugins in reverse dependency order, non-atomic JSON
writes that silently reset corrupt files, recursive placeholder expansion, shared mutable
placeholder caches, `asTextChannel()` failures in threads, voice chat and announcement channels,
and allow-all mentions.

## Differences from v3

Every deliberate difference, added by the change that introduces it.

| Area | v3 behavior | xincord behavior | Change |
|---|---|---|---|
| Config files | unknown keys fail the whole load (KAML strict mode) | unknown keys are logged as warnings | core-config |
| Core config | `general_settings` / `builtin_settings` with `TYPE;text;ms` strings | `token`, `status.activities`, `interaction_log`; migrate with `python -m xincord.core.migrate_v3 <dir>` | core-config |
| Status rotation | a `STREAMING` entry used its third field as both URL and delay, so nothing waited | separate `url` and `seconds` fields | core-config |
| Status rotation | malformed entries were skipped at runtime on every cycle | rejected when the config loads | core-config |
| Interaction log | unknown `log_type` values were ignored | validation error | core-config |
| Default core config | shipped a real guild and channel ID | ships no interaction log targets | core-config |
