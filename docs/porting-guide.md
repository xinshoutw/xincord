# Porting guide: XsDiscordBotKt to xincord

How Kotlin/JDA concepts map to Python/discord.py in this project, which ideas from the abandoned
v4 rewrite are kept, the traps found so far, and every place where xincord deliberately behaves
differently from v3. Update it after each Core change and each plugin.

Baseline: XsDiscordBotKt `main` at `3a59607` (v3.4). Decisions: `docs/porting/decisions.md`.

## Concept mapping

| Kotlin / JDA (v3) | Python / discord.py (xincord) | Decision |
|---|---|---|
| Plugin jar + `info.yaml`, classloader per plugin | extension module + `commands.Cog`, metadata as module constants (`DEPENDS`, `SOFT_DEPENDS`, `INTENTS`), entry point in group `xincord.plugins` named after the plugin | B2, B3 |
| `enabled` key in each plugin config | the core config's `plugins` list; `setup(bot)` calls `bot.plugin_context(__name__)` for `config(Model)` and `lang(locale)` | B3, B6 |
| "API plugins" (SQLiteAPI, GoogleSheetAPI, AudioAPI) | ordinary dependencies or nothing | B12 |
| `PluginEventConfigure.load()`: export lang, read config, build the `StringLocalizer` | `setup(bot)`: `context.lang(DEFAULT_LOCALE)`, `context.config(Config)`, `Templates.load(lang)`, then `bot.add_cog`, `bot.tree.add_command(cog.command())` and `bot.route` | B3 |
| `Placeholder.get(event)` / `Placeholder.get(member)` | `actor_values(interaction.user, bot) \| interaction_values(interaction)` / `actor_values(member, bot)`, plus the plugin's keys | B10 |
| Load order from `depend` / `soft_depend` | `graphlib.TopologicalSorter`; a failing plugin disables only itself | B3 |
| `GatewayIntent` presets | `discord.Intents` aggregated from enabled plugins before connecting | B4 |
| `ListenerAdapter` overrides | `@commands.Cog.listener()` | B3 |
| `CommandData` / `SlashCommandData` | `app_commands.command` / `app_commands.Group` | B5 |
| InteractionLogger's blanket `deferReply(true)` | `CommandTree.interaction_check` defers ephemerally; commands that open modals set `extras={"defer": False}` | B5 |
| `guildCommands()` / `globalCommands()` | guild commands by default, global with `extras={"global": True}` and JDA's default contexts set explicitly; `CommandTree.sync_global` / `sync_guild` upload only changed payloads | B5 |
| Command localization via `StringLocalizer` and Kotlin property paths | `app_commands.Translator` fed from `lang/<locale>/register.yaml` keys | B7 |
| `MessageCreator` YAML templates | templates module: v1 YAML tags and Components V2 | B10 |
| `Placeholder` / commons-text substitutor | single-level `%key%` substitution with a fresh context per render | B10 |
| `checkComponentIdPrefix` / `checkModalIdPrefix` in every plugin listener | `bot.route(__name__, ids, handler)` in `setup`; the handler gets the interaction and a `ParsedId` | B9 |
| `ComponentIdManager` (`{prefix}{a..z}:{value};...`) | `ComponentIds`: `{namespace}:1:{letter}={value};...` plus the permanent v3 decoder; `upgrade_view` rewrites legacy IDs | B9 |
| JSON files and embedded MongoDB | SQLite (`sqlite3` + `asyncio.to_thread`), key-value table plus per-plugin tables | B8 |
| kotlinx/Jackson YAML config | pydantic v2 models over PyYAML; unknown keys warn | B6 |
| Coroutines, `launch`, scheduled executors | `asyncio` tasks, `discord.ext.tasks.loop` | |
| JLine console (`JLineManager`, `JLineAppender`), `--ignore-update` | prompt_toolkit console (`xincord.core.console`; logs print above the prompt through `patch_stdout`), SIGHUP reload, `/xincord reload`; no version check | B15 |
| `Server/start`: `java -jar` with the token on the command line | `compose.yaml` and the `Dockerfile` image; the token goes in `bot/config.yaml` | B16 |
| `java -jar` with Clikt options | the `xincord` console script (`xincord.core.cli`, argparse); `--no-online` loads the plugins without connecting and exits | B15 |
| `BotLoader`: build JDA, wait for ready, then load the plugins | `Bot.setup_hook` sets the translator and loads the plugins before the gateway connects; `on_ready` and `on_guild_join` upload the commands | B3, B5 |
| `BotLoader.reload()`: stop JDA and start everything again | `Bot.reload(plugin=None)` in place: the loaded plugins follow `config.yaml`, or one plugin reloads with its dependents; triggered by SIGHUP, the owner's `/xincord reload` and the console | B15 |
| `StatusChanger` thread over `TYPE;text;ms` strings | `xincord.core.status.rotate` task, started on ready and restarted by a full reload | |
| `InteractionLogger` and `ConsoleLogger` listeners | `xincord.core.interaction_log.log` from `Bot.on_interaction`, after routing | |
| JDA's default mentions (all types ping) | the bot's `allowed_mentions`: users and the replied-to user; a message opts in with its own | B19 |
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

## Plugin conventions

Set by `port-example`; the full checklist is `.claude/skills/port-plugin/SKILL.md`, and _Example
(`xincord.plugins.example`) is the template to copy.

- One package per plugin, `xincord.plugins.<package>`: `__init__.py` (metadata constants and
  `setup`), `config.py`, `cog.py`, the bundled `config.yaml` and `lang/`. The entry point is named
  after the v3 plugin (`_Example = "xincord.plugins.example"`).
- Commands are built in `setup` from the plugin's Lang: `app_commands.Command` with the cog's
  bound method as the callback, then `rename` and `describe` on the command; names and
  descriptions default to v3's.
- Component IDs: `ComponentIds("<package>", <v3 fields in v3 order, then new ones>,
  legacy_prefix=<v3 prefix>)`, routed with `bot.route(__name__, IDS, handler)`.
- Placeholder keys keep v3's names, and v3's `Placeholder.get(...)` values come from the core
  families (see the mapping above).
- Tests live in `tests/plugins/<package>/` and load the real plugin through its entry point
  (`plugin_fakes.load_plugin`); Discord fakes are in `tests/support/discord_fakes.py`; v3's text
  per locale is golden data in `tests/fixtures/plugins/<package>/golden.yaml`.
- Logic that needs no Discord lives in its own module and is tested directly
  (`basic_calculator/calculator.py`); the cog only renders and sends. CPU-bound work runs in
  `asyncio.to_thread`.
- A plugin whose only v3 key was `enabled` ships no `config.yaml` (BasicCalculator).
- A v3 reply posted with `event.channel.sendMessage` goes to `interaction.channel` when it has a
  `send` method (BasicCalculator's `Postable` protocol: forums and categories have none), then the
  deferred response is deleted; on `discord.HTTPException` the reply replaces the deferred
  response instead.
- Recorded v3 answers (BasicCalculator's JSONL) are copied to `tests/fixtures/plugins/<package>/`
  unchanged. Records that a fixed v3 defect changes are checked against an independent
  implementation in the test, never edited.
- Gateway events are `@commands.Cog.listener()` methods on the cog, which discord.py adds and
  removes with it; `INTENTS` declares what they need (`discord.Intents(members=True)` for member
  events, AutoRole). Work that needs guild data runs from an `on_ready` listener and from
  `cog_load` when `bot.is_ready()`, because `on_ready` does not fire again for a plugin reloaded
  into a running bot; it skips guilds that are `unavailable`.
- A plugin without text ships no `lang/`, has no `DEFAULT_LOCALE` and never calls `context.lang`
  (AutoRole). Operator problems are `logger.warning` lines that name the plugin.
- Tests run listeners with `plugin_fakes.dispatch(bot, "<event>", *args)` and write an operator
  config with `plugin_fakes.load_plugin(..., config=...)`; `discord_fakes` has `FakeGuild`,
  `FakeRole` and `FakeMember` for member events.
- A v3 global command (`globalCommands()`) sets `extras={"global": True}` and JDA's defaults, which
  discord.py does not send: `allowed_contexts=AppCommandContext(guild=True, dm_channel=True,
  private_channel=False)` and `allowed_installs=AppInstallationType(guild=True, user=False)`
  (BotInfo).
- A config value that Discord would refuse at send time (a URL, a length) is validated in the
  model, so that the plugin fails at load with the key named (BotInfo's `source_url`).

## Pitfalls

- **Annotations at import time.** discord.py evaluates app-command parameter annotations when the
  decorator runs (PEP 649/749 make annotations lazy, but discord.py resolves them eagerly). Keep
  those imports at runtime; see `runtime-evaluated-decorators` in `pyproject.toml`.
- **Deprecation warnings.** pytest turns warnings into errors. discord.py 2.7.1 checks cog
  listeners (`Bot.add_listener`) and hooks with the deprecated `asyncio.iscoroutinefunction`;
  `pyproject.toml` ignores that warning from discord.py modules only.
- **Member removal.** `on_member_remove` fires only for cached members; use
  `on_raw_member_remove`.
- **Member joins.** `on_member_join` builds the member from the event, so it needs no member
  cache, but discord.py drops a join for a guild it has not cached or a member it already caches.
- **Roles.** JDA's `modifyMemberRoles(member, roles)` replaced every role; discord.py's
  `member.add_roles(role)` (atomic by default) sends one add-role request per role and keeps the
  others, while `atomic=False` sends one request computed from the cache. discord.py sends without
  JDA's client-side checks; `Role.is_assignable()` makes them (not `@everyone`, not managed, below
  the bot's highest role unless the bot owns the guild).
- **The members intent** is privileged: the bot's application must allow it in the developer
  portal, or the connection fails. With it, discord.py also downloads every guild's members before
  `on_ready` (`chunk_guilds_at_startup` follows the intent); v3 did not.
- **Unavailable guilds.** During an outage discord.py keeps a guild without roles or members, so
  `guild.me` is None there; check `guild.unavailable` before using guild data.
- **Member counts.** `Guild.member_count` stays current only with the members intent: discord.py
  updates it from member join and leave events. It is None for a guild unavailable since the bot
  connected. JDA's guild list left unavailable guilds out; `Client.guilds` keeps them.
- **Global command contexts.** discord.py sends `contexts` and `integration_types` only when a
  command sets them, and Discord's defaults then apply; JDA always sent guild and bot DM contexts
  and guild installs. Set them on ported global commands.
- **Events in tests.** `bot.dispatch` schedules listeners on the loop of a bot that logged in (a
  sentinel before that); tests await the listeners with `plugin_fakes.dispatch`.
- **Channel overwrites.** `create_text_channel(overwrites=...)` does not inherit the category's
  overwrites the way JDA does; merge them explicitly (Ticket).
- **IntervalPusher.** `tasks.loop` schedules from each start, not after each completion as Kotlin
  did. discord.py has no REST ping; time `GET /users/@me` to keep `%ping%`.
- **Exact decimals.** `decimal` defaults to 28 digits, and `Fraction` reduces with a gcd that costs
  75 to 180 ms per operation at 100,000 digits. BasicCalculator models Java's `BigDecimal` as an
  unscaled integer and a scale, which costs a few milliseconds there.
- **Big integers.** Python refuses `str()` and `int()` conversions of more than 4,300 digits
  (`ValueError`); bound the size before converting. Bound a power before computing it: Python
  computes `10**999999999` if asked.
- **Kotlin character classes.** `Char.isWhitespace()` is `str.isspace()` without U+0085;
  `Char.isDigit()` is `str.isdecimal()`; Kotlin strings are UTF-16, so v3 saw a character outside
  the BMP as two surrogates.
- **`str.splitlines()`** also splits at U+0085, U+2028 and other separators; split JSONL and other
  line-based data with `split("\n")`.
- **ruff S105** reports a variable or constant named like `token` that is compared with or assigned
  a string ("possible hardcoded password"); name it after what it holds instead.
- **CRLF in v3 files.** Some v3 resources have CRLF line endings (BasicCalculator's zh-TW
  `register.yaml`). Git stores them as LF, but the copied working file keeps CRLF; convert copied
  files to LF.
- **Lookup keys.** Kotlin's `StringLocalizer` uses camelCase property paths; Python uses the YAML
  keys directly.
- **CJK in tests.** Build samples with `chr(0x4E2D)` or YAML fixtures. Agent tools may decode a
  typed `\u` escape into the real character, which the CJK hook then rejects.
- **prek pygrep** compiles patterns as bytes, so a `\u` escape in a pattern fails; match UTF-8 byte
  ranges instead.
- **Plugin modules run twice.** Discovery imports a plugin to read its constants, and
  `load_extension` executes it again; keep import time free of work.
- **Setup runs before connecting.** A plugin's `setup` runs in `setup_hook`, before the gateway
  connects, so the guild cache is empty; with `--no-online` there is no login and `bot.user` is
  None too. Work that needs guilds waits for `bot.wait_until_ready()` in a task or listens for
  `on_ready`; background loops stop in `cog_unload`, because the offline check loads and
  unloads plugins without ever becoming ready.
- **Reload re-runs setup.** `reload_extension` executes the plugin module again and calls the new
  `setup`; release what the old version holds (tasks, listeners outside a cog) in `teardown` or
  `cog_unload`. A failed reload restores the old module and runs its `setup` again.
- **Command callbacks.** discord.py evaluates a callback's annotations when the command is built,
  so `import discord` must stay at runtime; ruff does not flag a move into `TYPE_CHECKING` while
  other `discord` imports remain, but the plugin then fails to load and its tests fail. Pass the
  cog's bound method: discord.py unwraps it and makes the cog the binding.
- **Real plugins in tests.** Unloading or reloading a real plugin makes discord.py re-import its
  modules, so classes imported by test modules no longer match; test reloads with fake plugins.
  A `setup` that raises (an invalid config, for example) also drops the plugin's modules from
  `sys.modules`: tests that load a plugin with a bad file look its cog up with `cast`, not an
  `isinstance` check against a class imported at collection (AutoRole's `test_config.py`). The
  tests that run after them load the new modules too, so the plugin's `cog` fixture also uses
  `cast` (BotInfo's `conftest.py`).
- **Stopped views.** A discord.py view created outside a running event loop never reports
  `is_finished()`; tests that check rendered views must be `async`.
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
| Storage | a JSON file that failed to parse was replaced by the default and saved | a corrupt database stops startup and is left untouched | core-storage |
| Storage | JSON files written in place; save errors only logged | SQLite transactions; a failed write raises | core-storage |
| Lang files | a `register.yaml` that failed to decode was logged and its locale dropped | the plugin fails to load with the file and key named | core-i18n |
| Lang files | an invalid localized command name surfaced as a failed registration | rejected when the lang files load | core-i18n |
| Lang keys | Kotlin camelCase property paths (`basicCalculate.name`) | YAML paths (`basic-calculate.name`) | core-i18n |
| Placeholders | substituted values were expanded again (user text could inject placeholders; a self-reference dropped the message) | values are inserted verbatim in one pass | core-placeholders |
| Placeholders | per-user substitutors cached in shared maps, keeping every custom key ever set | each render builds its own values | core-placeholders |
| Placeholders | `guild_owner_id` / `guild_owner_mention` were `0` / `-` unless the owner member was cached | taken from `Guild.owner_id` | core-placeholders |
| Templates | a locale directory missing one template raised at render time | per-file fallback to the default locale | core-templates |
| Templates | render-time values were added to the shared global substitutor for good | values apply to one render only | core-templates |
| Templates | bad styles, missing `uid`s and bad timestamps failed when a message was sent | they fail when the plugin loads | core-templates |
| Components V2 | V2 components were checked when a message was rendered | validated when the plugin loads | core-components-v2 |
| Components V2 | without `is_components_v2`, a top-level `model_key` in `components_v2` could supply a whole action row | only action rows there; models work inside them | core-components-v2 |
| Components V2 | an embed model's timestamp became ISO text in the container footer | Discord `<t:...:f>` markup, shown in the reader's time zone | core-components-v2 |
| Component IDs | values containing `:` or `;` could not be parsed back | values are percent-encoded | core-component-ids |
| Component IDs | values went through the shared placeholder substitutor | values are written verbatim | core-component-ids |
| Component IDs | no version; old IDs had to stay valid forever | versioned; legacy IDs still parse and are rewritten when first used | core-component-ids |
| Plugin loading | plugins loaded in reverse dependency order | dependencies load first | core-plugin-loading |
| Plugin loading | one plugin's broken config or lang file could stop the whole bot | only that plugin and its dependents are skipped | core-plugin-loading |
| Plugin switches | an `enabled` key in each plugin config, checked by every handler; disabled plugins still exported their files | the core config's `plugins` list; disabled plugins are never imported | core-plugin-loading |
| Intents | GUILD_MEMBERS always requested | requested only when an enabled plugin declares it | core-plugin-loading |
| Command upload | guild commands overwritten in every guild at every start | uploaded only when a scope's payload hash changed, or when forced | core-command-tree |
| Component routing | every plugin received every component and modal event and filtered by prefix | only the owning plugin's handler runs; a message is upgraded to new IDs after a legacy one is used | core-component-routing |
| Placeholders | `channel_category_name` came from `asTextChannel()`, which failed for commands in threads, voice-channel chats and announcement channels | taken from any channel's category, for components too | core-interaction-values |
| Placeholders | `component_url` was defined but always absent: link buttons send no interactions | not provided | core-interaction-values |
| Command line | `--no-online` read the core config, then idled with the console open | loads the config and the plugins without connecting, then exits with 0, or 1 if a plugin did not load | core-startup |
| Command line | logback level names; an unknown name silently became DEBUG | Python level names in any case; an unknown name is a usage error | core-startup |
| Command line | `--ignore-update` (`-I`) and `--auto-defer-interactions` / `--no-auto-defer-interactions` | removed: no version check, and commands opt out of the defer with `extras` | core-startup |
| Logging | also written to `log/output.log`, rotated at 1 MB | stderr only | core-startup |
| Startup | the token was compared with a placeholder string | the default token is empty; `--token` overrides the config | core-startup |
| Startup | plugins loaded after JDA was ready, so `setup` could read the guild cache | plugins load before the gateway connects | core-startup |
| Command upload | guild commands were uploaded at startup only when there were any, so the last removed one stayed | an empty payload is uploaded once | core-startup |
| Mentions | every mention type pinged, including `@everyone` and roles | users and the replied-to user only, unless a message opts in | core-startup |
| Reload | the console's `reload` disconnected and rebuilt everything; a plugin that failed stayed off | reloads in place without disconnecting; a plugin whose new version fails keeps its previous one | core-reload |
| Reload | only the console (whole bot) or the Web Dashboard (one plugin) could reload | SIGHUP and the owner's `/xincord reload [plugin]` (the console follows) | core-reload |
| Console | started without a terminal too, and end of input stopped the bot | runs only when stdin and stdout are terminals | core-console |
| Console | `reload` took no plugin and completion covered the command names | `reload <plugin>`, and the loaded plugins complete after `reload` | core-console |
| Interaction log | modal submissions were posted to log channels with `cl_type` `BTN` | `MODAL` | core-status-log |
| Interaction log | log channel messages used JDA's default mentions, so `%user_mention%` pinged | log messages never ping | core-status-log |
| Status rotation | a single activity was set again after every delay | set once | core-status-log |
| Deployment | `java -jar` from `Server/`, files and MongoDB data next to the jar | an arm64 image under docker compose: files in `./bot`, the SQLite database in the `xincord_data` volume | container |
| _Example | an `option1` longer than 1024 characters overflowed the embed field, and the command got no reply | Discord refuses more than 1024 characters | port-example |
| _Example | no reply in threads, voice channel chats and announcement channels | answers in any channel | port-example |
| _Example | `%...%` in the options was expanded, and a self-reference made the reply fail | option text is inserted as typed | port-example |
| _Example | the `_Example@` keys stayed in the user's cached placeholders | each render uses its own values | port-example |
| _Example | `example_key` was required but never read; a config without it stopped the bot | optional, `example_value` by default, shown in the reply | port-example |
| _Example | the reply needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers the command | port-example |
| _Example | the reply was the embed alone | a third field shows `example_key`, and a button under the embed counts presses | port-example |
| BasicCalculator | a minus after an operator subtracted from a synthetic `0` (`2*-3` was `-3`, `2^-1` was `0`, `1/-2` divided by zero) | it negates (`-6`, `0.5`, `-0.5`) | port-basic-calculator |
| BasicCalculator | `^` grouped from the left (`2^3^2` was 64) | from the right (512) | port-basic-calculator |
| BasicCalculator | `^` truncated its exponent to 32 bits (`2^0.5` was 1, `2^4294967297` was 2) | whole exponents only: `Exponent must be an integer` or `Too many digits` | port-basic-calculator |
| BasicCalculator | division by zero and negative or huge exponents threw, and "thinking..." stayed | an error embed; negative exponents divide 1 by the power | port-basic-calculator |
| BasicCalculator | no limits: `10^999999999` stalled the gateway thread, and formulas or results over 1018 characters got no reply | `formula` takes at most 1018 characters, numbers over 50,000 digits fail with `Too many digits`, and the calculation runs in a worker thread | port-basic-calculator |
| BasicCalculator | `%...%` in a failing formula was expanded, and `%bc_question%` gave no reply | the formula is shown as typed | port-basic-calculator |
| BasicCalculator | the `bc_` keys stayed in the member's cached placeholders | each render uses its own values | port-basic-calculator |
| BasicCalculator | `%bc_answer_round%` was the whole answer | the part before the decimal point | port-basic-calculator |
| BasicCalculator | "thinking..." stayed when the bot could not post in the channel | the answer replaces the deferred response | port-basic-calculator |
| BasicCalculator | the en-US `formula` description said "bracket is ignorable" | it says that the multiplication sign can be omitted | port-basic-calculator |
| BasicCalculator | the reply needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers the command | port-basic-calculator |
| BasicCalculator | an unknown character outside the BMP was reported as half a surrogate pair | the whole character | port-basic-calculator |
| AutoRole | `modifyMemberRoles` replaced the member's roles with the configured ones, so a role another bot gave at the join could be removed | each configured role is added with its own request; the member keeps every other role | port-auto-role |
| AutoRole | roles were looked up in every guild, and another guild's role made JDA refuse every role | roles are looked up in the joined guild; another guild's role is skipped and logged | port-auto-role |
| AutoRole | one role the bot could not give (managed, `@everyone`, too high) or a missing Manage Roles meant no role at all | such a role is skipped with a warning and the others are given; without Manage Roles one warning names the guild | port-auto-role |
| AutoRole | roles were resolved once, at the first join, so later roles and guilds needed a reload | roles are looked up at each join | port-auto-role |
| AutoRole | unknown role IDs were dropped without a log, and other problems showed only at a join | warnings when the bot is ready, when the plugin loads into a ready bot, and at each join | port-auto-role |
| AutoRole | a reload replaced the guild set and the role map one after the other, so a join in between could fail | a reload replaces the whole cog | port-auto-role |
| AutoRole | the bundled `config.yaml` held real guild and role IDs | it lists no guilds and shows placeholder IDs in a comment | port-auto-role |
| BotInfo | `member_counts` and `guild_counts` were written into the shared global placeholders at each use, so every plugin's later renders saw them | the counts are values of one render | port-bot-info |
| BotInfo | the reply needed the core's auto-defer, which `--no-auto-defer-interactions` turned off | the command tree always defers the command | port-bot-info |
| BotInfo | guilds that became unavailable during an outage were left out of both counts | they count as guilds, with the members discord.py knew | port-bot-info |
| BotInfo | no source link; the bundled `config.yaml` held only `enabled: false` | a Source Code field shows `source_url` (decision C3), by default the xincord repository, checked when the plugin loads | port-bot-info |
