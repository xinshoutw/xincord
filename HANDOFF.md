# HANDOFF: xincord Phase 2 (implementation)

Updated 2026-10-10 after `port-basic-calculator`, the second plugin port. Core is complete. Read
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
    `interaction_values` with JDA's `command_string`), Protocols that discord.py classes satisfy,
    and JDA locale names (`resources/locales.yaml`, `locale_names`).
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
  `tests/conftest.py`. When a second plugin needs v3's `Placeholder.get(event)`, move the
  example's `placeholder_values` into `xincord.core.placeholders`.
- **BasicCalculator** (`xincord.plugins.basic_calculator`, no config): `calculator.py` is a pure
  evaluator with v3's shunting-yard pass and `BigDecimal` results (`BigDecimal(unscaled, scale)`),
  v3's defects fixed and size limits; `cog.py` runs it in `asyncio.to_thread`, posts the answer to
  the channel (`_post`: a `runtime_checkable` `Postable` protocol, fallback to the deferred
  response on `discord.HTTPException`) and edits errors into the deferred response. Reuse:
  `discord_fakes.FakeChannel`, `forbidden()` and `delete_original_response`; the golden pattern
  for recorded v3 answers with an independent evaluator (`tests/plugins/basic_calculator/
  test_golden.py`).
- **Still to build:** the plugins after BasicCalculator (section 5).

## 5. Status and next steps

### Done (archived, pushed, CI green)

`project-skeleton`, `core-config`, `core-storage`, `core-i18n`, `core-placeholders`,
`core-templates`, `core-components-v2`, `core-component-ids`, `core-plugin-loading`,
`core-command-tree`, `core-component-routing`, `core-interaction-values`, `core-startup`,
`core-reload`, `core-console`, `core-status-log`, `container`, `port-example`,
`port-basic-calculator`. Each one's `design.md` in `openspec/changes/archive/` records its
decisions and "v3 behaved differently" notes; `docs/porting-guide.md` has the differences table.

### Next: the plugins

Core is complete; _Example (the template) and BasicCalculator are ported. Next: **AutoRole**
(`port-auto-role`). Port the plugins in C1 order with the `port-plugin` skill
(`.claude/skills/port-plugin/SKILL.md`), one OpenSpec change each (`port-<plugin-kebab>`):
_Example (done), BasicCalculator (done), then AutoRole,
BotInfo (with the configurable AGPL source link, C3), SimpleCommand, WelcomeByeGuild,
IntervalPusher, Feedbacker, Economy, DynamicVoiceChannel, VoiceLogger, ChatLogger, Giveaway,
Ticket, TicketAddons, NtustManager, NtustCourse, MusicPlayer (with Lavalink in `compose.yaml`).
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
  `isinstance` checks fail.
- `str.splitlines()` also splits at U+0085 and U+2028: split JSONL with `split("\n")`. Kotlin's
  `isWhitespace()` is `str.isspace()` without U+0085.
- ruff S105 reports names like `token` compared with or assigned a string; rename them.
- Some v3 resources have CRLF line endings; git stores LF but the copied working file keeps CRLF.
- A stub whose annotations use `discord` keeps the import under `TYPE_CHECKING` until code uses it
  at runtime, or ruff's TC rules fail the gate.
- Python 3.14 accepts `except A, B:` without parentheses, and ruff formats it that way.

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

**v3 behaviors never to reproduce:** loading plugins in reverse dependency order, non-atomic JSON
writes that reset corrupt files, recursive placeholder expansion, shared mutable placeholder
caches, `asTextChannel()` failures in threads, voice chat and announcement channels, allow-all
mentions.

**Exact numbers (BasicCalculator):** `decimal` defaults to 28 digits, and `Fraction` reduces with a
gcd that costs 75 to 180 ms per operation at 100,000 digits; scaled integers (v3's `BigDecimal`)
cost a few milliseconds. Python refuses `str()`/`int()` conversions over 4,300 digits and computes
`10**999999999` if asked: bound sizes first.

**Kotlin lookup keys:** v3 used camelCase property paths; xincord uses the YAML keys.
