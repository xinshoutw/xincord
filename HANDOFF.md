# HANDOFF: xincord Phase 2 (implementation)

Updated 2026-10-10 after `port-interval-pusher`, the seventh plugin port. Core is complete. Read
this file first, then `docs/porting/decisions.md` and `AGENTS.md`. The decisions are accepted and
binding; do not re-open them unless you find a serious problem, and then ask the owner.

Talk to the owner in Traditional Chinese. Everything written into the repository is English.

## 1. Goal

Port XsDiscordBotKt (Kotlin + JDA 6, about 20.4k lines: Core 5.9k, 21 plugin modules 13.9k) to
Python 3.14 + uv as **xincord**, managing specs with OpenSpec and building everything test-first,
starting with Core. Motivation: easier maintenance and faster iteration.

## 2. Where things are

| What | Where |
|---|---|
| This project | `/Users/xinshou/IdeaProjects/xincord`, branch `main`, pushed to `origin` |
| Remote (private) | `git@github.com:xinshoutw/xincord.git`; CI: `.github/workflows/ci.yml` |
| Kotlin baseline | `/Users/xinshou/IdeaProjects/XsDiscordBotKt` at `3a59607` (branch `main`) |
| Accepted decisions | `docs/porting/decisions.md`; raw submission in `docs/porting/submissions/` |
| Project rules | `AGENTS.md` (there is deliberately no CLAUDE.md) |
| Porting guide and v3 differences | `docs/porting-guide.md` |
| Specs | `openspec/specs/` (archived), `openspec/changes/` (active) |
| Per-plugin inventories (acceptance-criteria source, with Kotlin `file:line`) | `docs/porting/analysis/inventory/<Plugin>.md` |
| BasicCalculator golden data | `docs/porting/analysis/inventory/fixtures/*.jsonl` |
| Research (versions, v4 branch, Core brief) | `docs/porting/analysis/research/*.md` |
| Kotlin v4 design spec (summarized in the porting guide) | `XsDiscordBotKt/docs/specs/2026-04-07-v4-core-refactor-design.md` |
| Local data copy for a future migration test (B11, deferred) | `XsDiscordBotKt/Server/` |

## 3. Rules

`AGENTS.md` holds the full rules. The essentials:

- Language: replies to the owner in Traditional Chinese; repository content in English; zero CJK
  characters in `*.py` (a prek hook enforces it); commit messages ASCII only.
- Commits: Conventional Commits with scopes `core`, `build`, `ci`, `docs`, `plugin-<name>`;
  GPG-signed; no attribution lines (the commit-msg hook rejects them); small and frequent; every
  commit passes `scripts/gate.sh`.
- TDD (A11, xfail-first): failing test committed with `@pytest.mark.xfail(strict=True,
  raises=NotImplementedError, reason="<requirement>")` against a stub, then the implementation
  commit removes the marker. Each test names its requirement in a docstring
  (`"""Requirement: <name>."""`) or in the module docstring.
- OpenSpec: one active change at a time; archive right after verification; every scenario has a
  test; requirement descriptions stay under 500 characters (`validate --strict` fails otherwise).
- Pushing `main` to `origin` is pre-authorized. Ask first for force pushes, deleting branches,
  tags, releases, PyPI publishing, repository settings, and anything on the XsDiscordBotKt remote.
- Do not create LICENSE (the owner adds it). Never commit real IDs, bank account numbers or tokens
  as defaults.
- List user-visible changes (copy, commands, interaction flow) for the owner before pushing them.

## 4. Architecture as built so far

- **Layout (resolution 2, amended):** a uv workspace. The root project is the `xincord`
  distribution (`src/xincord/core/`, `module-name = "xincord.core"`); `packages/xincord-plugins`
  is the `xincord-plugins` distribution (`src/xincord/plugins/`). `xincord` is a PEP 420 namespace;
  `xincord.plugins` is a regular package.
- **Gate:** `scripts/gate.sh` runs ruff check, ruff format check, pyright strict, coverage + pytest
  (branch coverage >= 85%, currently 100%) and `openspec validate --all --strict`. prek runs it on
  pre-push; the Claude Code Stop hook runs it too; CI runs it on every push.
- **Core modules (all archived and green):**
  - `xincord.core.config`: `load_config`, `parse_model`, `unknown_keys`, `Model`, `ConfigError`,
    the core schema `CoreConfig` (`token`, `plugins`, `status.activities`, `interaction_log`) and
    the default `resources/config.yaml`. `xincord.core.migrate_v3` converts the v3 core config and
    lists the plugins whose v3 config had `enabled: true` (`python -m xincord.core.migrate_v3 <dir>`).
  - `xincord.core.storage`: `Store` over one SQLite connection on one worker thread; JSON values by
    namespace and key; `update` (atomic read-modify-write), `run` (plugin tables), `lock(key)`.
  - `xincord.core.i18n`: `export_lang`, `Lang.load` (locales, flattened YAML keys, Discord name
    rules, key-set warnings), `Lang.text` / `Lang.template` (fallback), `Lang.localization` (no
    fallback), `Lang.command` and `Translator`.
  - `xincord.core.placeholders`: single-pass `render`, the v3 key families (`actor_values`,
    `user_values`, `member_values`, `guild_values`, `channel_values`, `event_values`,
    `interaction_values` with JDA's `command_string`), `placeholder_values(interaction)` (v3's
    `Placeholder.get(event)`: the acting user's keys with the bot's and the interaction's),
    Protocols that discord.py classes satisfy (`EventLike` and `ClientLike` for interactions), and
    JDA locale names (`resources/locales.yaml`, `locale_names`). A thread whose parent channel is
    not cached gives no `channel_category_name` (discord.py's `Thread.category` raises there).
  - `xincord.core.templates` (package: `base`, `schema`, `schema_v2`, `render`, `render_v2`,
    `__init__`): v1 message templates, Components V2 and modal templates, validated at load
    (`load_message`, `load_modal`, `Templates.load`) and rendered to
    `Message(content, embeds, view, files)` and `discord.ui.Modal`. V2 mode renders a
    `discord.ui.LayoutView`; `files` carries the uploads that `file_path` media need.
  - `xincord.core.component_ids`: `ComponentIds(namespace, fields, legacy_prefix=, legacy_hex=)`
    builds `{namespace}:1:{letter}={value};...` (percent-encoded, 100 characters max; `build` is
    the templates' `build_id`), parses new and v3 IDs into text fields (`ParsedId.legacy`), and
    `upgrade` / `upgrade_view` rewrite legacy IDs in a view rebuilt with `from_message`.
  - `xincord.core.plugins`: `discover(enabled)` reads entry points (group `xincord.plugins`, name =
    plugin name) and the module constants `DEPENDS`, `SOFT_DEPENDS`, `INTENTS`, drops broken
    plugins, missing dependencies and cycles, and orders the rest with `graphlib`;
    `required_intents`; `PluginContext` (`directory`, `store`, `config(Model)`, `lang(locale)`).
  - `xincord.core.bot.Bot(commands.Bot)`: created from the discovered plugins with their intents;
    `load_plugins()` (isolated failures, dependents skipped), `plugin_context(__name__)` for a
    plugin's `setup(bot)`, `load_plugin(info)` (hot load: refuses new intents or missing
    dependencies), `reload_plugin(name)` (with dependents; discord.py keeps the old version on
    failure), `route(__name__, ids, handler)` and `on_interaction`, which sends component and
    modal interactions to the owning plugin's handler with a `ParsedId` and, after a legacy ID,
    fetches the message, runs `upgrade_view` and edits it once. `setup_hook` sets the
    `Translator` and loads the plugins before the gateway connects; `on_ready` syncs the global
    commands and every guild's, `on_guild_join` forces the new guild's; the default
    `allowed_mentions` ping users and the replied-to user only (B19). `reload(plugin=None)`
    returns a one-line summary: without a plugin it re-reads `CORE_CONFIG`, unloads plugins that
    left the list (dependents first), reloads the loaded ones and loads new ones; with a plugin it
    reloads it and its dependents. Reloads are serialized by a lock and upload every scope with
    force when the bot is ready.
  - `xincord.core.admin.Xincord`: the global, guild-only `/xincord` group (administrators see it by
    default); `reload [plugin]` runs for the application owner only and replies ephemerally with
    the summary; `plugin` autocompletes loaded plugins. `setup_hook` registers it.
  - `xincord.core.cli`: the `xincord` console script. `parse_args` (`--token`, `--level`,
    `--no-online`, `--force-renew-lang-resources` with v3's short forms) returns `Options`;
    `run(options)` loads `config.yaml`, opens `data/xincord.db`, discovers `CoreConfig.plugins`
    and either checks them offline (`--no-online`: load, unload, exit 0 or 1) or connects until
    SIGINT or SIGTERM closes the bot and the store; SIGHUP runs `bot.reload()`. Logs go to stderr
    only. On a terminal (not `--no-online`), `main` sets up logging inside
    `patch_stdout(raw=True)` and `_serve` runs the console task, cancelled when the bot stops.
  - `xincord.core.console`: `run_console(bot, stop)` (prompt `console > `; `reload [plugin]`,
    `stop` / `exit` / `shutdown` and ^D call `stop`, ^C is logged) and `completer(bot)`.
  - `xincord.core.status`: `activity(entry)` and `rotate(client, activities)`; the bot keeps the
    core config (`Bot(..., config=)`), starts the rotation on ready, restarts it after a full
    reload and cancels it in `close`.
  - `xincord.core.interaction_log`: `describe(interaction)` (v3's CMD, MSG, BTN, STRING, ENTITY,
    MODAL) and `log(client, interaction, targets)`, called by `Bot.on_interaction` after routing:
    a console line, then the matching `interaction_log` targets via `get_partial_messageable`,
    never pinging.
  - `xincord.core.command_tree.CommandTree` (the bot's `tree_cls`): `interaction_check` defers
    application commands ephemerally unless `extras["defer"]` is False; `payloads()` splits
    guild commands from `extras["global"]` ones (translated when a translator is set);
    `sync_global(store)` / `sync_guild(store, guild_id, force=)` upload only when the payload's
    SHA-256 changed (stored in the `core` namespace) and log failures.
    Component and modal IDs come from a `build_id(uid_map)` callable the plugin passes in. Views
    and modals are stopped before they are returned, so discord.py never dispatches their
    interactions; the core will route them (Core change `command-tree`).
- **Deployment (`container`):** `Dockerfile` (two stages on `python:3.14.8-slim-trixie`, uv 0.12.24,
  `uv sync --locked --no-dev --all-packages --no-editable`, user `xincord` in `/bot`, entry point
  `xincord`), `.dockerignore`, and `compose.yaml` (service `bot`: `./bot` bind-mounted at `/bot`,
  named volume `data` = `xincord_data` at `/bot/data`, `stdin_open`, `tty`, `init`,
  `restart: unless-stopped`, 30 s stop grace, json-file logs 10 MB x 3).
- **Plugins (`packages/xincord-plugins`):** `xincord.plugins.example` (entry point `_Example`), the
  template: `__init__.py` (metadata constants, `setup`), `config.py`, `cog.py` (commands built in
  `setup` from the Lang with the cog's bound method as callback, `IDS = ComponentIds("example",
  ("action", "count"))` routed with `bot.route`), bundled `config.yaml` and `lang/`. Conventions
  for every port: `.claude/skills/port-plugin/SKILL.md`. Reuse in tests: `plugin_fakes.load_plugin`
  (real entry point, offline), `plugin_fakes.golden(<package>)`, `tests/support/discord_fakes.py`
  (`FakeInteraction` records `sent`; `buttons`, `embed_dict`); the `store` fixture is in
  `tests/conftest.py`. The example's `placeholder_values` moved into `xincord.core.placeholders`
  with WelcomeByeGuild.
- **BasicCalculator** (`xincord.plugins.basic_calculator`, no config): `calculator.py` is a pure
  evaluator with v3's shunting-yard pass and `BigDecimal` results (`BigDecimal(unscaled, scale)`),
  v3's defects fixed and size limits; `cog.py` runs it in `asyncio.to_thread`, posts the answer to
  the channel (`_post`: a `runtime_checkable` `Postable` protocol, fallback to the deferred
  response on `discord.HTTPException`) and edits errors into the deferred response. Reuse:
  `discord_fakes.FakeChannel`, `forbidden()` and `delete_original_response`; the golden pattern
  for recorded v3 answers with an independent evaluator (`tests/plugins/basic_calculator/
  test_golden.py`).
- **AutoRole** (`xincord.plugins.auto_role`, `INTENTS = discord.Intents(members=True)`, no lang):
  an `on_member_join` cog listener adds each configured role with its own atomic `add_roles`
  request (v3 replaced all roles), skipping and logging roles that are missing or not
  `is_assignable()`; `check()` logs config problems from `on_ready` and from `cog_load` when the
  bot is already ready. Reuse: `plugin_fakes.dispatch(bot, event, *args)` for listeners,
  `load_plugin(..., config=...)`, `discord_fakes.FakeGuild` / `FakeRole` / `FakeMember`, and the
  ready-check pattern for any plugin that needs guild data at startup.
- **BotInfo** (`xincord.plugins.bot_info`, `INTENTS = discord.Intents(members=True)` for current
  member counts): the first global command, `extras={"global": True}` with JDA's default contexts
  and install types set explicitly (`allowed_contexts`, `allowed_installs`); `counts(guilds)` is a
  pure function over `interaction.client.guilds`; the reply renders `bot-info` with values of one
  render (`guild_counts`, `member_counts`, `source_url`, v3's `bot_id` and `bot_name`).
  `config.yaml` has `source_url` (C3, default the xincord repository), validated at load as an
  http(s) URL of at most 512 characters. Reuse: `FakeGuild(member_count=...)`, a `FakeInteraction`
  whose `client` is `SimpleNamespace(user=BOT_USER, guilds=[...])`, the global payload check in
  `tests/plugins/bot_info/test_command.py`, and a `cast`-based `cog` fixture for a plugin whose
  tests load invalid configs.
- **SimpleCommand** (`xincord.plugins.simple_command`, no intents, no config, zh-TW only): five
  guild commands from the `COMMANDS` table (`command(name)` with
  `app_commands.default_permissions(administrator=True)`) share the callback `post_message`, which
  reads `interaction.command.name`, renders that template in `lang.default_locale` with v3's
  `bot_id` and `bot_name`, posts the whole message (content, embeds, view and files) through
  `_postable` (the channel as `object` against the `Postable` Protocol) and `_send`, then deletes
  the deferred response; when the channel takes no messages or refuses it, it renders again and
  edits the deferred response, with the files as `attachments`. The bundled templates hold the
  example account number `000000000000`. Reuse: `FakeInteraction(command=SimpleNamespace(name=...))`
  and `ClosingChannel` (`tests/plugins/simple_command/test_post.py`) for discord.py's closed files.
  `_bot_values` now exists in BotInfo and SimpleCommand: a third plugin that needs v3's global keys
  moves it into `xincord.core.placeholders`.
- **WelcomeByeGuild** (`xincord.plugins.welcome_bye_guild`, `INTENTS = discord.Intents(members=True)`,
  no config, en-US and zh-TW): the first plugin with data. `store.py` keeps v3's per-guild document
  (`{"welcomeChannelId", "byeChannelId"}`, 0 = unbound) in the key-value table under the namespace
  `WelcomeByeGuild` and the guild ID, read without writing and changed by `set_channel` under
  `store.lock("WelcomeByeGuild:<id>")`; `values.py` builds v3's `wbg@` keys from the core families
  (`command_values`, `member_event_values`) and checks text channels with a `runtime_checkable`
  Protocol; `cog.py` has four guild commands with two shared callbacks (`bind_channel`,
  `unbind_channel`, kind from the `COMMANDS` table), a `TextChannelOption` transformer that limits
  the option to text channels (`channel_types` [0]), the runtime Administrator check through
  `interaction.permissions`, replies in `interaction.guild_locale`, `on_member_join`,
  `on_raw_member_remove` (skips the bot's own removal) and `on_guild_remove`, and
  `forget_left_guilds` from `on_ready` and `cog_load`. Reuse: the per-guild data convention (skill,
  "Storage"), `FakeGuild(channels=..., preferred_locale=..., icon=..., rules_channel=...)` with
  `get_channel` and `as_guild()`, `FakeChannel(type=...)`, `FakeMember` with placeholder
  attributes, `FakeInteraction(guild=, guild_locale=, permissions=)`, `Bot.user` patched as a
  property, and the scratch probe through discord.py's own objects (skill step 7).
- **IntervalPusher** (`xincord.plugins.interval_pusher`, no intents, no lang, config
  `listeners[].url` and `interval`): the first background loop and outgoing HTTP. `pusher.py` has
  `Pusher(number, listener, get, ping, sleep)`, v3's loop with its effects passed in (push at once,
  then `interval` seconds after each attempt; a 404 ends it; failures are logged), `rest_ping`
  (times `bot.http.request(Route("GET", "/users/@me"))`, JDA's REST ping) and aiohttp's
  `open_session` and `get_status` (no redirects, v3's timeouts); `xincord-plugins` declares aiohttp.
  `cog.py` creates one task per listener in `cog_load`, each awaiting `bot.wait_until_ready()`, and
  cancels and awaits them in `cog_unload`. Reuse: `plugin_fakes.Ready` (READY for offline bots; its
  `close` cancels the tasks left running), `http_fakes.running_monitor()` (`Monitor`, a local HTTP
  server), patching `discord.http.HTTPClient.request` to record REST calls, an injected `sleep`
  with a fake clock, `bot.remove_cog` to run `cog_unload` without unloading the modules, and the
  REST probe through `Route.BASE` and `http.static_login` (skill step 7).
- **Still to build:** the plugins after IntervalPusher (section 5).

## 5. Status and next steps

### Done (archived, pushed, CI green)

`project-skeleton`, `core-config`, `core-storage`, `core-i18n`, `core-placeholders`,
`core-templates`, `core-components-v2`, `core-component-ids`, `core-plugin-loading`,
`core-command-tree`, `core-component-routing`, `core-interaction-values`, `core-startup`,
`core-reload`, `core-console`, `core-status-log`, `container`, `port-example`,
`port-basic-calculator`, `port-auto-role`, `port-bot-info`, `port-simple-command`,
`port-welcome-bye-guild`, `port-interval-pusher`. Each one's
`design.md` in `openspec/changes/archive/` records its decisions and "v3 behaved differently"
notes; `docs/porting-guide.md` has the differences table.

### Next: the plugins

Core is complete; _Example (the template), BasicCalculator, AutoRole, BotInfo, SimpleCommand,
WelcomeByeGuild and IntervalPusher are ported. Next: **Feedbacker** (`port-feedbacker`). Port the
plugins in C1 order with the `port-plugin` skill (`.claude/skills/port-plugin/SKILL.md`), one
OpenSpec change each (`port-<plugin-kebab>`): _Example (done), BasicCalculator (done), AutoRole
(done), BotInfo (done, with the configurable AGPL source link of C3), SimpleCommand (done),
WelcomeByeGuild (done), IntervalPusher (done), then Feedbacker, Economy, DynamicVoiceChannel,
VoiceLogger, ChatLogger, Giveaway, Ticket, TicketAddons, NtustManager, NtustCourse, MusicPlayer
(with Lavalink in `compose.yaml`).
Update `docs/porting-guide.md` after each one.

### Working tips from this session

- Template tests that check rendered views must be `async`: a discord.py view created outside a
  running event loop never reports `is_finished()`.
- Core plugin tests use `FakePlugins` (`tests/support/plugin_fakes.py`, on the pytest and pyright
  paths) through the `fake_plugins` fixture in `tests/core/conftest.py` and the `store` fixture in
  `tests/conftest.py`: it writes plugin packages to a temporary `sys.path` entry and builds entry
  points; their `calls` list survives reloads. Discovery and `load_extension` both execute a plugin
  module. Real plugins load with `plugin_fakes.load_plugin` (see the port-plugin skill).
- Startup tests (`tests/core/test_startup.py`) patch `importlib.metadata.entry_points` and
  `Bot.start`, `chdir` into `tmp_path`, and send real signals with `signal.raise_signal`: the
  handlers that `run` installs turn them into `bot.close()`.
- discord.py component objects for fakes can be built from payloads (`discord.ActionRow(payload)`,
  `discord.Container(payload, None)`); `View.from_message` only reads `message.components`.
- An xfail stub for a new schema field: a property that raises `NotImplementedError` keeps pyright
  happy until the field exists.
- Test commands with `app_commands.Command(name=..., callback=...)` in a typed factory: decorated
  module-level commands are partially unknown to pyright.
- Docker: the CLI uses the OrbStack context; the engine is usually stopped. Ask before `orb start`,
  and `orb stop` afterwards. `docker compose run --rm -T bot --no-online` checks an image without a
  token; `docker compose down -v` removes the test volume.
- Run the gate and check its exit status directly. Piping it into `tail` before `&&` once hid a
  failure and let a bad commit through (it was amended before pushing).
- OpenSpec is not installed globally: `OPENSPEC_TELEMETRY=0 npx --yes @fission-ai/openspec@1.14.1
  <command> </dev/null`. Telemetry is also off in `~/.config/openspec/config.json`.
- Per change: propose, `validate --strict`, commit; xfail and implementation commits; porting-guide
  rows; push; `gh run watch <id> --exit-status`; `archive <name> --yes`; `validate --all --strict`;
  commit; push.

## 6. Open items for the owner

Answered on 2026-10-10: the license is `AGPL-3.0-or-later` (set in both `pyproject.toml` files;
the owner still adds LICENSE); OpenSpec stays on npx; the user-visible changes listed before were
accepted. For `core-startup` the owner chose: `--no-online` checks and exits; logs go to stderr
only (no log file). For `core-reload`: English copy for `/xincord`, and a full reload unloads the
plugins removed from the list. The `core-console`, `core-status-log` and `container` behavior was
accepted as listed. Still open: a run with a real token under compose (step 3 of the manual check
in `openspec/changes/archive/2026-10-10-container/design.md`).

From the plugin ports on, the owner asked for pushes without waiting for review: each port lists
its user-visible changes, the choices made without the owner and the manual checks in
`docs/porting/owner-review.md`, which the owner reviews afterwards.

1. **Review (pushed in core-plugin-loading):** plugins are enabled in the core `config.yaml`
   (`plugins: [AutoRole, ...]`) instead of each plugin's `enabled` key, and the migration script
   fills that list; plugins that are not enabled no longer create files under `plugins/<Name>/`;
   the privileged members intent is requested only when an enabled plugin needs it.
2. **Production version (F1)** is unknown; it matters only if a data migration is ever needed.
3. **Lavalink image** (arm64, compose details) and **VoiceLogger status events** (audit types
   192/193, maybe raw gateway handling): verify when those plugins start.

## 7. Verified facts and pitfalls

**Versions in use (2026-10-10):** Python 3.14.8 (uv-managed), uv 0.12.24, ruff 0.16.10, pyright
1.1.414, pytest 9.1.1, pytest-asyncio 1.4.0, coverage 7.16.2, prek 0.5.5, OpenSpec 1.14.1,
discord.py 2.7.1, pydantic 2.14.0, PyYAML 6.0.3. Actions are pinned by SHA: checkout v7.0.1,
setup-uv v10.2.0, setup-node v7.1.0.

**Tooling pitfalls**
- Agent tools may decode a typed `\u` escape followed by hex digits into the real character.
  Build non-ASCII test data with `chr(0x4E2D)` or YAML fixtures; the CJK hook catches mistakes.
- prek refuses to install while a global `core.hooksPath` is set; this clone uses
  `git config --local core.hooksPath .git/hooks`. The owner's global commit-msg hook (which strips
  attribution lines) therefore does not run here; the project hook rejects such lines instead.
- prek `pygrep` compiles patterns as bytes: match UTF-8 byte ranges, never `\u` escapes.
- `importlib.import_module("xincord")` instead of `import xincord`: pyright reports the namespace
  package as a missing stub.
- Long Kotlin citations in docstrings exceed the line limit; put each path on its own line.
- Annotate `@asynccontextmanager` functions as returning `AsyncGenerator` (typeshed deprecates
  `AsyncIterator` there).
- YAML 1.1 reads a bare `no` as false: quote locale keys (`"no": ...`).
- `openspec/config.yaml` rules containing `: ` must be quoted.
- After an entry point is added to `packages/xincord-plugins/pyproject.toml`, `uv run` reinstalls
  the editable package; `uv.lock` does not change.
- uv_build wheels include the package's data files. Without Docker, check packaging with
  `uv build --package xincord-plugins` and `xincord --no-online` from a scratch venv holding both
  wheels.
- Tests must not unload or reload a real plugin: discord.py re-imports its modules and later tests'
  `isinstance` checks fail. A `setup` that raises (an invalid config) also drops the plugin's
  modules from `sys.modules`; tests that load bad files look the cog up with `cast`, and so does
  the plugin's `cog` fixture, because the tests that run after them get the new classes.
- A conditional expression on one line (`{} if bot is None else ...`) adds no branch for coverage;
  the plugins' `client.user is None` fallbacks stay on one line, so branch coverage stays at 100%.
- discord.py's `Bot.add_listener` (every cog listener) calls the deprecated
  `asyncio.iscoroutinefunction`; `pyproject.toml` ignores that DeprecationWarning from `discord.`
  modules in pytest, which otherwise turned it into a failed plugin load.
- `bot.dispatch` needs a bot that logged in (`Client.loop` is a sentinel before), and so does
  `bot.wait_until_ready()`; tests await listeners with `plugin_fakes.dispatch`.
- `str.splitlines()` also splits at U+0085 and U+2028: split JSONL with `split("\n")`. Kotlin's
  `isWhitespace()` is `str.isspace()` without U+0085.
- ruff S105 reports names like `token` compared with or assigned a string; rename them.
- Some v3 resources have CRLF line endings; git stores LF but the copied working file keeps CRLF.
- A stub whose annotations use `discord` keeps the import under `TYPE_CHECKING` until code uses it
  at runtime, or ruff's TC rules fail the gate.
- Python 3.14 accepts `except A, B:` without parentheses, and ruff formats it that way.
- ruff's TRY400 wants `logger.exception` for `logger.error` inside `except` (`# noqa: TRY400`
  where a traceback is noise), and TRY401 refuses the exception object in `logger.exception`.
- aiohttp's `RawTestServer.close()` waits for the requests still in flight: answer them first, or
  the teardown waits for the client's timeout (`http_fakes.Monitor.close`). Autouse fixtures are
  torn down after the fixtures a test requests.
- `asyncio.CancelledError` is a `BaseException`: `except Exception` leaves cancellation alone.
  Kotlin's `catch (e: Exception)` caught `CancellationException`.

**discord.py 2.7.1 facts**
- Decorators evaluate app-command annotations at import time; keep those imports at runtime
  (`runtime-evaluated-decorators` in `pyproject.toml`).
- `send`, interaction replies and `send_modal` store a view or modal for dispatch only if it is
  not finished; templates stop theirs.
- `TextInput(label=...)` is deprecated; wrap inputs in `discord.ui.Label` (as JDA 6's `Label.of`).
  discord.py's own deprecation helper can bypass `filterwarnings = ["error"]`, so watch pytest's
  "N warnings" line.
- `PartialEmoji.from_str` treats `<:name:id>` as custom only when the ID has 13 to 20 digits.
- `discord.ChannelType` has no 14 (JDA's `GUILD_DIRECTORY`).
- `isinstance` rejects subscripted generics such as `discord.ui.Button[View]`; check the bare
  class and `cast`.
- `on_member_remove` only fires for cached members; use `on_raw_member_remove`.
  `on_member_join` builds the member from the event (no member cache needed), but discord.py drops
  a join for an uncached guild or an already cached member.
- `member.add_roles(role)` is atomic by default: one `PUT .../roles/{id}` per role, keeping the
  other roles; `atomic=False` sends one PATCH computed from the cache. discord.py sends without
  JDA's client-side checks; `Role.is_assignable()` makes them.
- With the members intent, discord.py chunks every guild before `on_ready`
  (`chunk_guilds_at_startup` follows the intent). An unavailable guild (outage) is cached without
  roles or members, so `guild.me` is None there.
- `Guild.member_count` stays current only with the members intent (discord.py updates it from
  member join and leave events); it is None for a guild unavailable since the bot connected.
  `Client.guilds` keeps unavailable guilds; JDA's guild list left them out.
- A command sends `contexts` and `integration_types` only when it sets `allowed_contexts` and
  `allowed_installs`, and Discord's defaults apply otherwise; JDA always sent the guild and bot DM
  contexts and guild installs, which ported global commands set explicitly.
- `create_text_channel(overwrites=...)` does not copy the category's overwrites as JDA does.
- `tasks.loop` schedules from each start; there is no REST ping (time `GET /users/@me`).
- `app_commands.Command(callback=cog.method)` unwraps the bound method and makes the cog the
  command's binding (`cog_app_command_error` and the cog's `interaction_check` apply).
  `app_commands.rename(...)` and `describe(...)` also work on a built `Command`. discord.py
  evaluates the callback's annotations when the command is built, so `import discord` stays at
  runtime; ruff's non-strict TC rules accept a move into `TYPE_CHECKING` while other `discord`
  imports remain, and only the plugin's tests catch it.
- Unloading an extension removes the tree commands whose callback module belongs to it
  (`_remove_with_module`), including commands added in `setup` with `bot.tree.add_command`.
- `interaction.response.edit_message(view=...)` keeps the message's content and embeds.
  `Embed.to_dict()` adds `type` and `flags`.
- Components V2 classes exist: `LayoutView`, `Container`, `Section`, `TextDisplay`, `Thumbnail`,
  `MediaGallery` (`discord.MediaGalleryItem`), `Separator` (`SeparatorSpacing`), `File`,
  `ActionRow`; buttons take `sku_id`.
- `send` and the interaction edits close a message's `File` objects when they finish, even when
  Discord refused the request (`MultipartParameters.__exit__`): render again before sending the
  message elsewhere. An unclosed `discord.File` in a test fails it
  (`PytestUnraisableExceptionWarning`).
- `Messageable.send` overloads take `view: View` with content and embeds, or `view: LayoutView`
  without them; `View | LayoutView | None` matches none. `isinstance` against a Protocol keeps each
  member of `interaction.channel`'s union with its own overloads (and pyright reports an unsafe
  overlap): pass the channel as `object` first (SimpleCommand's `_postable`).
- `app_commands.default_permissions(administrator=True)` also applies to a built `Command`; the
  payload's `default_member_permissions` is then the integer 8.
- A `discord.TextChannel` option annotation sends `channel_types` [0, 5] (announcement channels
  too) and resolves the channel from the cache; a `Transformer` with `channel_types` [text] over
  `AppCommandChannel` sends [0] and takes what Discord resolved. `Transform[...] | None` works as an
  optional parameter. discord.py's `TextChannel` also stands for announcement channels: check
  `.type`.
- `Thread.category` raises `ClientException` when the parent channel is not cached, which
  `getattr(..., None)` does not catch; `interaction_values` handles it now.
- In a guild, `interaction.guild` is never None: discord.py builds a placeholder guild (no channels,
  name `''`) when it has not cached the guild. `interaction.guild_locale` and
  `interaction.permissions` come straight from the payload; the guild owner and administrators
  get every permission there.
- `on_raw_member_remove` is dispatched for every removal, even for an uncached guild; its `user` is
  the cached `Member` when there was one. JDA ignored the bot's own removal.
- At `on_ready`, `Client.guilds` holds every guild of READY, unavailable ones included (READY adds
  them before their GUILD_CREATE), so stored data of other guilds belongs to guilds the bot left.
- `wait_until_ready` raises until `login` or `async with bot` creates the READY event; the
  `--no-online` check enters `async with bot`, so loops wait for a READY that never comes, and
  `Bot.close` unloads the extensions (running `cog_unload`) before it closes the HTTP client.
- `HTTPClient.request(Route(...))` is the REST call behind discord.py's methods; it retries a 500,
  502, 504 or 524 (and a reset connection) up to five times, sleeping 1 + 2 x tries seconds, then
  raises `DiscordServerError`.
- A probe can log in offline: point `discord.http.Route.BASE` at a local server and call
  `bot.http.static_login(token)` inside `async with bot`; set `bot._ready` for READY.
- A scratch probe can drive real discord.py objects offline: set `bot._connection.user` to a
  `ClientUser`, build `discord.Interaction(data=..., state=bot._connection)` and call
  `command._invoke_with_namespace(...)` (patch `Interaction.edit_original_response`); set
  `bot.loop`, add a guild with `state._add_guild_from_data(...)` and call `state.parse_*` for
  gateway events (patch `Messageable.send`).

**v3 behaviors never to reproduce:** loading plugins in reverse dependency order, non-atomic JSON
writes that reset corrupt files, recursive placeholder expansion, shared mutable placeholder
caches, `asTextChannel()` failures in threads, voice chat and announcement channels, allow-all
mentions.

**Exact numbers (BasicCalculator):** `decimal` defaults to 28 digits, and `Fraction` reduces with a
gcd that costs 75 to 180 ms per operation at 100,000 digits; scaled integers (v3's `BigDecimal`)
cost a few milliseconds. Python refuses `str()`/`int()` conversions over 4,300 digits and computes
`10**999999999` if asked: bound sizes first.

**Kotlin lookup keys:** v3 used camelCase property paths; xincord uses the YAML keys.
